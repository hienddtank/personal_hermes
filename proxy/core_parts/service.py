import copy
import json
import random
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from fastapi.responses import JSONResponse

from .config import (
    CAPTURE_CLIENT_CHUNKS,
    CAPTURE_DIR,
    CAPTURE_FAILURES,
    CAPTURE_MAX_CHARS,
    CAPTURE_RAW_CHUNKS,
    CAPTURE_SAMPLE_RATE,
    DEFAULT_INTERCEPT_MODE,
    DEFAULT_LMSTUDIO_BASE_URL,
    DEFAULT_PROXY_MODE,
    DEFAULT_VISIBLE_REASONING,
    ENABLE_BUILTIN_EXECUTE_CODE,
    ENABLE_BUILTIN_TOOLS,
    ENABLE_TOOL_INTENT_REPAIR,
    LAST_PROXY_JSON_LOG_PRUNE,
    MAX_TOOL_INTENT_REPAIR_ATTEMPTS,
    MAX_TOOL_ITERATIONS,
    PROXY_JSON_LOG_DIR,
    PROXY_JSON_LOG_PRUNE_INTERVAL_SECONDS,
    PROXY_JSON_LOG_RETENTION_DAYS,
    PROXY_RESUME_FORMAT,
    TOOL_EXECUTOR_URL,
    TOOL_INTENT_REPAIR_CONTEXT_CHARS,
    TOOL_INTENT_REPAIR_MAX_TOKENS,
    UPSTREAM_CONNECT_TIMEOUT_SECONDS,
    UPSTREAM_TIMEOUT_SECONDS,
    UPSTREAM_TOOL_FORMAT,
    XML_TOOL_RESPONSE_ROLE,
    logger,
)
from proxy.observability.contract_validator import validate_non_stream_response
from proxy.observability.failure_capture import CaptureContext, capture_failure_sample
from .executor import ToolExecutor
from .models import SessionState, StreamState, ToolCall, ToolExecutionResult
from .parsing import (
    ToolCallParser,
    append_native_tool_delta,
    consume_native_tool_calls,
    native_tool_calls_from_message,
)
from .payload_utils import (
    append_stream_response_line,
    append_tool_results_to_payload,
    build_empty_resume_fallback,
    build_repair_source_text,
    build_text_chat_completion_response,
    build_tool_intent_repair_prompt,
    dedupe_reasoning_prefix,
    new_stream_response_log,
    normalize_assistant_resume_content,
    normalize_lmstudio_base_url,
    reset_session_turn_state,
    response_assistant_text,
    response_has_tool_calls,
    safe_log_slug,
    should_attempt_tool_intent_repair,
    tail_text,
    tool_execution_available,
    tool_signature,
    truncate_text,
    validate_and_sanitize_tool_calls,
)
from .rewriting import (
    chunk_base_from,
    content_chunk_from,
    finish_chunk_from,
    rewrite_request_for_upstream,
    safe_json_response,
    sse_data,
    sse_done,
    tool_call_chunk_from,
)
from .state_machine import StreamStateMachine
from .text_utils import (
    remove_control_tags,
    tool_call_block_is_structural_in_text,
    tool_call_open_is_structural_in_text,
)


def build_tool_intent_repair_payload(
    payload: Dict[str, Any],
    session: SessionState,
    assistant_text: str,
) -> Dict[str, Any]:
    repair_payload = copy.deepcopy(rewrite_request_for_upstream(payload, session.policy))
    messages = copy.deepcopy(repair_payload.get("messages") or [])
    cleaned_assistant_text = tail_text(
        remove_control_tags(assistant_text),
        TOOL_INTENT_REPAIR_CONTEXT_CHARS,
    )
    if cleaned_assistant_text.strip():
        messages.append({"role": "assistant", "content": cleaned_assistant_text.strip()})
    messages.append(
        {
            "role": "user",
            "content": build_tool_intent_repair_prompt(session.policy.get("tools", [])),
        }
    )
    repair_payload["messages"] = messages
    repair_payload["stream"] = True
    repair_payload["temperature"] = 0
    existing_max_tokens = repair_payload.get("max_tokens")
    if isinstance(existing_max_tokens, int) and existing_max_tokens > 0:
        repair_payload["max_tokens"] = min(existing_max_tokens, TOOL_INTENT_REPAIR_MAX_TOKENS)
    else:
        repair_payload["max_tokens"] = TOOL_INTENT_REPAIR_MAX_TOKENS
    attempts = int(payload.get("_proxy_tool_intent_repair_attempts", 0) or 0)
    repair_payload["_proxy_tool_intent_repair_attempts"] = attempts + 1
    return rewrite_request_for_upstream(repair_payload, session.policy)


class LMStudioProxy:
    def __init__(
        self,
        lmstudio_base_url: str = DEFAULT_LMSTUDIO_BASE_URL,
        intercept_mode: bool = DEFAULT_INTERCEPT_MODE,
        enable_logging: bool = True,
    ):
        self.lmstudio_base_url = normalize_lmstudio_base_url(lmstudio_base_url)
        self.intercept_mode = intercept_mode
        self.enable_logging = enable_logging
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                UPSTREAM_TIMEOUT_SECONDS,
                connect=UPSTREAM_CONNECT_TIMEOUT_SECONDS,
            )
        )
        self.tool_executor = ToolExecutor(self.client)
        self.sessions: Dict[str, SessionState] = {}
        self.metrics: Dict[str, int] = {
            "requests_total": 0,
            "stream_requests_total": 0,
            "non_stream_requests_total": 0,
            "orchestrator_requests_total": 0,
            "resume_generations_total": 0,
            "tool_calls_parsed_total": 0,
            "tool_executions_total": 0,
            "tool_execution_errors_total": 0,
            "malformed_outputs_total": 0,
            "upstream_errors_total": 0,
            "max_tool_iterations_total": 0,
            "tool_intent_repairs_total": 0,
            "tool_intent_repair_success_total": 0,
            "tool_intent_repair_failures_total": 0,
            "json_logs_saved_total": 0,
            "json_log_errors_total": 0,
            "json_logs_pruned_total": 0,
        }
        self._prune_old_json_logs(force=True)

    async def close(self) -> None:
        await self.client.aclose()

    async def handle_chat_completion(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        request_id = str(uuid.uuid4())
        session = SessionState(request_id=request_id)
        self.sessions[request_id] = session
        self.metrics["requests_total"] += 1
        try:
            policy = self.select_policy(payload)
            session.policy = policy
            if self.enable_logging:
                self._log_request(request_id, payload, policy)
                self._save_json_log(
                    request_id,
                    direction="incoming",
                    stage="client_request",
                    payload=payload,
                    extra={"policy": policy},
                )
            if payload.get("stream", False):
                self.metrics["stream_requests_total"] += 1
                return self._stream_chat_completion(payload, session, headers or {})
            self.metrics["non_stream_requests_total"] += 1
            return await self._non_stream_chat_completion(payload, session, headers or {})
        except Exception as exc:
            self._capture_failure(
                session,
                payload,
                failure_type="PROXY_EXCEPTION",
                message="exception inside proxy request handling",
                exception=exc,
            )
            self.sessions.pop(request_id, None)
            raise

    def select_policy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        tools = payload.get("tools", [])
        proxy_mode = str(payload.get("proxy_mode", DEFAULT_PROXY_MODE)).strip().lower()
        pass_through = proxy_mode in {"pass-through", "passthrough", "transparent"}
        parse_only = proxy_mode in {"parse-only", "parse_only", "mode1", "intercept"}
        can_execute_tools = tool_execution_available()
        orchestrator = proxy_mode in {"orchestrator", "orchestrate", "mode2", "mode-2", "local", "execute"}
        if DEFAULT_PROXY_MODE in {"orchestrator", "orchestrate", "mode2", "mode-2", "local", "execute"} and not pass_through and not parse_only:
            orchestrator = True
        actual_proxy_mode = proxy_mode
        if orchestrator and not can_execute_tools:
            logger.warning(
                "PROXY_MODE=%s requested, but no tool executor is configured; falling back to parse-only so Hermes can execute tools.",
                proxy_mode,
            )
            orchestrator = False
            parse_only = True
            actual_proxy_mode = "parse-only"
        return {
            "tools": tools,
            "has_tools": len(tools) > 0,
            "intercept_tools": bool(tools) and self.intercept_mode and not pass_through,
            "visible_reasoning": DEFAULT_VISIBLE_REASONING,
            "hide_raw_tool_xml": True,
            "execute_tools_locally": bool(tools) and self.intercept_mode and orchestrator and not pass_through,
            "resume_after_tool": bool(tools) and self.intercept_mode and orchestrator and not pass_through,
            "pass_through": pass_through or not self.intercept_mode,
            "proxy_mode": actual_proxy_mode,
            "requested_proxy_mode": proxy_mode,
            "tool_execution_available": can_execute_tools,
            "resume_format": PROXY_RESUME_FORMAT,
            "max_tool_iterations": MAX_TOOL_ITERATIONS,
        }

    async def _non_stream_chat_completion(
        self,
        payload: Dict[str, Any],
        session: SessionState,
        headers: Dict[str, str],
    ) -> JSONResponse:
        if session.policy.get("execute_tools_locally") and session.policy.get("resume_after_tool"):
            self.metrics["orchestrator_requests_total"] += 1
            return await self._non_stream_orchestrated(payload, session, headers)
        upstream_payload = rewrite_request_for_upstream(payload, session.policy)
        self._save_json_log(
            session.request_id,
            direction="forwarded",
            stage="non_stream_upstream",
            payload=upstream_payload,
            extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
        )
        response = await self.client.post(
            f"{self.lmstudio_base_url}/v1/chat/completions",
            json=upstream_payload,
            headers=headers,
        )
        if response.status_code >= 400:
            self.metrics["upstream_errors_total"] += 1
            self._capture_failure(
                session,
                payload,
                failure_type="BACKEND_ERROR_STATUS",
                message=f"upstream error status {response.status_code}",
            )
            self.sessions.pop(session.request_id, None)
            return JSONResponse(status_code=response.status_code, content=safe_json_response(response))
        body = safe_json_response(response)
        if not body:
            self._capture_failure(
                session,
                payload,
                failure_type="EMPTY_UPSTREAM_BODY",
                message="empty upstream response body",
            )
        if session.policy.get("intercept_tools"):
            self._normalize_non_stream_response(body, session)
            if not response_has_tool_calls(body):
                assistant_text = response_assistant_text(body)
                repaired_tool_calls = await self._repair_tool_intent(payload, session, headers, assistant_text)
                if repaired_tool_calls:
                    self._apply_tool_calls_to_non_stream_response(body, session, assistant_text, repaired_tool_calls)
        self._capture_non_stream_contract_issues(session, payload, body)
        self.sessions.pop(session.request_id, None)
        return JSONResponse(status_code=response.status_code, content=body)

    async def _stream_chat_completion(
        self,
        payload: Dict[str, Any],
        session: SessionState,
        headers: Dict[str, str],
    ) -> AsyncIterator[str]:
        try:
            if session.policy.get("pass_through") or not session.policy.get("intercept_tools"):
                async for event in self._relay_stream_pass_through(payload, session, headers):
                    yield event
                return
            if session.policy.get("execute_tools_locally") and session.policy.get("resume_after_tool"):
                self.metrics["orchestrator_requests_total"] += 1
                async for event in self._relay_stream_orchestrated(payload, session, headers):
                    yield event
                return
            async for event in self._relay_stream_with_interception(payload, session, headers):
                yield event
        finally:
            self.sessions.pop(session.request_id, None)

    async def _relay_stream_pass_through(self, payload: Dict[str, Any], session: SessionState, headers: Dict[str, str]) -> AsyncIterator[str]:
        stream_payload = {**rewrite_request_for_upstream(payload, session.policy), "stream": True}
        response_log = new_stream_response_log()
        self._save_json_log(
            session.request_id,
            direction="forwarded",
            stage="stream_pass_through_upstream",
            payload=stream_payload,
            extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
        )
        try:
            async with self.client.stream("POST", f"{self.lmstudio_base_url}/v1/chat/completions", json=stream_payload, headers=headers) as response:
                response_log["status_code"] = response.status_code
                if response.status_code >= 400:
                    self.metrics["upstream_errors_total"] += 1
                    response_log["error"] = "upstream error"
                    self._capture_failure(
                        session,
                        payload,
                        failure_type="BACKEND_ERROR_STATUS",
                        message=f"upstream error status {response.status_code}",
                        response_log=response_log,
                    )
                    yield sse_data({"error": "upstream error", "status_code": response.status_code})
                    yield sse_done()
                    return
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        append_stream_response_line(response_log, line)
                        yield line + "\n\n"
        finally:
            self._capture_stream_invariants(session, payload, response_log, "")
            self._save_json_log(
                session.request_id,
                direction="upstream_response",
                stage="stream_pass_through_response",
                payload=response_log,
                extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
            )

    async def _relay_stream_with_interception(self, payload: Dict[str, Any], session: SessionState, headers: Dict[str, str]) -> AsyncIterator[str]:
        stream_payload = {**rewrite_request_for_upstream(payload, session.policy), "stream": True}
        response_log = new_stream_response_log()
        self._save_json_log(
            session.request_id,
            direction="forwarded",
            stage="stream_intercept_upstream",
            payload=stream_payload,
            extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
        )
        machine = StreamStateMachine(session, session.policy)
        assistant_text_parts: List[str] = []
        terminal_chunks: List[Dict[str, Any]] = []
        try:
            async with self.client.stream("POST", f"{self.lmstudio_base_url}/v1/chat/completions", json=stream_payload, headers=headers) as response:
                response_log["status_code"] = response.status_code
                if response.status_code >= 400:
                    self.metrics["upstream_errors_total"] += 1
                    response_log["error"] = "upstream error"
                    self._capture_failure(
                        session,
                        payload,
                        failure_type="BACKEND_ERROR_STATUS",
                        message=f"upstream error status {response.status_code}",
                        response_log=response_log,
                    )
                    yield sse_data({"error": "upstream error", "status_code": response.status_code})
                    yield sse_done()
                    return
                last_chunk: Dict[str, Any] = {
                    "id": f"chatcmpl-{session.request_id}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": payload.get("model", ""),
                    "choices": [{"index": 0}],
                }
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    append_stream_response_line(response_log, line)
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        output = machine.flush()
                        if output.text_delta:
                            assistant_text_parts.append(output.text_delta)
                            yield sse_data(content_chunk_from(last_chunk, output.text_delta))
                        repaired_tool_calls = await self._repair_tool_intent(
                            payload,
                            session,
                            headers,
                            build_repair_source_text(assistant_text_parts, session.raw_text_buffer),
                        )
                        if repaired_tool_calls:
                            self.metrics["tool_calls_parsed_total"] += len(repaired_tool_calls)
                            for index, tool_call in enumerate(repaired_tool_calls):
                                self._log_tool_parse_result(session.request_id, tool_call)
                                openai_tool = ToolCallParser.convert_to_openai_tool_call(tool_call, index=index)
                                yield sse_data(tool_call_chunk_from(last_chunk, openai_tool))
                            yield sse_data(finish_chunk_from(last_chunk, "tool_calls"))
                            yield sse_done()
                            session.current_state = StreamState.FINAL_ANSWER
                            return
                        if output.is_malformed:
                            self.metrics["malformed_outputs_total"] += 1
                            yield sse_data({"error": "malformed tool call", "request_id": session.request_id})
                        else:
                            for terminal_chunk in terminal_chunks:
                                yield sse_data(terminal_chunk)
                        yield sse_done()
                        session.current_state = StreamState.FINAL_ANSWER
                        return
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("[%s] malformed upstream SSE JSON: %r", session.request_id, data_str)
                        yield line + "\n\n"
                        continue
                    last_chunk = chunk
                    choices = chunk.get("choices") or []
                    choice = choices[0] if choices else {}
                    delta = choice.get("delta") or {}
                    finish_reason = choice.get("finish_reason")
                    native_tool_calls = delta.get("tool_calls")
                    if native_tool_calls:
                        yield sse_data(chunk)
                        continue
                    reasoning_delta = delta.get("reasoning_content") or ""
                    if reasoning_delta:
                        output = machine.advance_state(reasoning_delta)
                        if output.is_malformed:
                            self.metrics["malformed_outputs_total"] += 1
                            yield sse_data({"error": "malformed tool call", "request_id": session.request_id})
                            yield sse_done()
                            return
                        if output.tool_call:
                            self.metrics["tool_calls_parsed_total"] += 1
                            self._log_tool_parse_result(session.request_id, output.tool_call)
                            openai_tool = ToolCallParser.convert_to_openai_tool_call(output.tool_call)
                            yield sse_data(tool_call_chunk_from(chunk, openai_tool))
                            yield sse_data(finish_chunk_from(chunk, "tool_calls"))
                            yield sse_done()
                            return
                        if session.current_state != StreamState.TOOL_CAPTURE:
                            yield sse_data(chunk)
                        continue
                    text_delta = delta.get("content") or ""
                    if not text_delta:
                        if finish_reason or not choices or not delta:
                            terminal_chunks.append(chunk)
                        else:
                            yield sse_data(chunk)
                        continue
                    output = machine.advance_state(text_delta)
                    if output.is_malformed:
                        self.metrics["malformed_outputs_total"] += 1
                        yield sse_data({"error": "malformed tool call", "request_id": session.request_id})
                        yield sse_done()
                        return
                    if output.text_delta:
                        assistant_text_parts.append(output.text_delta)
                        yield sse_data(content_chunk_from(chunk, output.text_delta))
                    if output.tool_call:
                        self.metrics["tool_calls_parsed_total"] += 1
                        self._log_tool_parse_result(session.request_id, output.tool_call)
                        openai_tool = ToolCallParser.convert_to_openai_tool_call(output.tool_call)
                        yield sse_data(tool_call_chunk_from(chunk, openai_tool))
                        yield sse_data(finish_chunk_from(chunk, "tool_calls"))
                        yield sse_done()
                        return
        finally:
            self._capture_stream_invariants(session, payload, response_log, "".join(assistant_text_parts))
            response_log["assistant_text"] = "".join(assistant_text_parts)
            response_log["raw_text_buffer"] = session.raw_text_buffer
            response_log["normalized_text_buffer"] = session.normalized_text_buffer
            response_log["events"] = session.events
            self._save_json_log(
                session.request_id,
                direction="upstream_response",
                stage="stream_intercept_response",
                payload=response_log,
                extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
            )

    async def _relay_stream_orchestrated(self, payload: Dict[str, Any], session: SessionState, headers: Dict[str, str]) -> AsyncIterator[str]:
        current_payload = copy.deepcopy(rewrite_request_for_upstream(payload, session.policy))
        current_payload["stream"] = True
        last_tool_calls: List[ToolCall] = []
        last_tool_results: List[ToolExecutionResult] = []
        for iteration in range(session.policy.get("max_tool_iterations", MAX_TOOL_ITERATIONS) + 1):
            reset_session_turn_state(session)
            machine = StreamStateMachine(session, session.policy)
            assistant_text_parts: List[str] = []
            detected_tool_calls: List[ToolCall] = []
            last_chunk: Dict[str, Any] = {
                "id": f"chatcmpl-{session.request_id}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": payload.get("model", ""),
                "choices": [{"index": 0}],
            }
            response_log = new_stream_response_log()
            self._save_json_log(
                session.request_id,
                direction="forwarded",
                stage=f"stream_orchestrated_upstream_iteration_{iteration}",
                payload=current_payload,
                extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
            )
            async with self.client.stream("POST", f"{self.lmstudio_base_url}/v1/chat/completions", json=current_payload, headers=headers) as response:
                response_log["status_code"] = response.status_code
                if response.status_code >= 400:
                    self.metrics["upstream_errors_total"] += 1
                    response_log["error"] = "upstream error"
                    self._capture_failure(
                        session,
                        payload,
                        failure_type="BACKEND_ERROR_STATUS",
                        message=f"upstream error status {response.status_code}",
                        response_log=response_log,
                    )
                    self._save_stream_response_log(session, f"stream_orchestrated_response_iteration_{iteration}", response_log, assistant_text_parts)
                    yield sse_data({"error": "upstream error", "status_code": response.status_code})
                    yield sse_done()
                    return
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    append_stream_response_line(response_log, line)
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        output = machine.flush()
                        if output.text_delta:
                            assistant_text_parts.append(output.text_delta)
                            yield sse_data(content_chunk_from(last_chunk, output.text_delta))
                        repaired_tool_calls = await self._repair_tool_intent(
                            current_payload,
                            session,
                            headers,
                            build_repair_source_text(assistant_text_parts, session.raw_text_buffer),
                        )
                        if repaired_tool_calls:
                            detected_tool_calls = repaired_tool_calls
                            break
                        if output.is_malformed:
                            self.metrics["malformed_outputs_total"] += 1
                            yield sse_data({"error": "malformed tool call", "request_id": session.request_id})
                        elif iteration > 0 and last_tool_results and not "".join(assistant_text_parts).strip():
                            fallback_text = build_empty_resume_fallback(last_tool_calls, last_tool_results)
                            assistant_text_parts.append(fallback_text)
                            yield sse_data(content_chunk_from(last_chunk, fallback_text))
                        yield sse_done()
                        session.current_state = StreamState.FINAL_ANSWER
                        self._capture_stream_invariants(session, payload, response_log, "".join(assistant_text_parts))
                        self._save_stream_response_log(session, f"stream_orchestrated_response_iteration_{iteration}", response_log, assistant_text_parts)
                        return
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("[%s] malformed upstream SSE JSON: %r", session.request_id, data_str)
                        continue
                    last_chunk = chunk
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    finish_reason = choice.get("finish_reason")
                    native_tool_calls = delta.get("tool_calls")
                    if native_tool_calls:
                        append_native_tool_delta(session, native_tool_calls)
                        if finish_reason == "tool_calls":
                            detected_tool_calls = consume_native_tool_calls(session)
                            break
                        continue
                    if finish_reason == "tool_calls" and session.native_tool_call_parts:
                        detected_tool_calls = consume_native_tool_calls(session)
                        break
                    reasoning_delta = delta.get("reasoning_content") or ""
                    if reasoning_delta:
                        output = machine.advance_state(reasoning_delta)
                        if output.is_malformed:
                            self.metrics["malformed_outputs_total"] += 1
                            yield sse_data({"error": "malformed tool call", "request_id": session.request_id})
                            yield sse_done()
                            self._capture_stream_invariants(session, payload, response_log, "".join(assistant_text_parts))
                            self._save_stream_response_log(session, f"stream_orchestrated_response_iteration_{iteration}", response_log, assistant_text_parts)
                            return
                        if output.tool_call:
                            detected_tool_calls = [output.tool_call]
                            break
                        continue
                    text_delta = delta.get("content") or ""
                    if not text_delta:
                        continue
                    output = machine.advance_state(text_delta)
                    if output.is_malformed:
                        self.metrics["malformed_outputs_total"] += 1
                        yield sse_data({"error": "malformed tool call", "request_id": session.request_id})
                        yield sse_done()
                        self._capture_stream_invariants(session, payload, response_log, "".join(assistant_text_parts))
                        self._save_stream_response_log(session, f"stream_orchestrated_response_iteration_{iteration}", response_log, assistant_text_parts)
                        return
                    if output.text_delta:
                        assistant_text_parts.append(output.text_delta)
                        yield sse_data(content_chunk_from(chunk, output.text_delta))
                    if output.tool_call:
                        detected_tool_calls = [output.tool_call]
                        break
            self._save_stream_response_log(session, f"stream_orchestrated_response_iteration_{iteration}", response_log, assistant_text_parts)
            self._capture_stream_invariants(session, payload, response_log, "".join(assistant_text_parts))
            if not detected_tool_calls:
                yield sse_done()
                return
            if iteration >= session.policy.get("max_tool_iterations", MAX_TOOL_ITERATIONS):
                self.metrics["max_tool_iterations_total"] += 1
                yield sse_data(content_chunk_from(last_chunk, "\nProxy stopped after the maximum tool-call iterations."))
                yield sse_done()
                return
            self.metrics["tool_calls_parsed_total"] += len(detected_tool_calls)
            for tool_call in detected_tool_calls:
                self._log_tool_parse_result(session.request_id, tool_call)
            tool_results = await self._execute_tool_calls(session, payload, detected_tool_calls)
            last_tool_calls = detected_tool_calls
            last_tool_results = tool_results
            assistant_reasoning = session.reasoning_buffer.strip()
            assistant_content = dedupe_reasoning_prefix("".join(assistant_text_parts), assistant_reasoning)
            append_tool_results_to_payload(current_payload, assistant_content, assistant_reasoning, detected_tool_calls, tool_results)
            self.metrics["resume_generations_total"] += 1
            session.current_state = StreamState.RESUME
        self.metrics["max_tool_iterations_total"] += 1
        yield sse_data({"error": "maximum tool-call iterations exceeded"})
        yield sse_done()

    async def _execute_tool_calls(self, session: SessionState, payload: Dict[str, Any], tool_calls: List[ToolCall]) -> List[ToolExecutionResult]:
        results: List[ToolExecutionResult] = []
        tool_schema = ToolCallParser.tool_schema_from_openai_tools(session.policy.get("tools", []))
        for tool_call in tool_calls:
            self.metrics["tool_executions_total"] += 1
            if not ToolCallParser.validate_tool_call(tool_call, tool_schema):
                result = ToolExecutionResult(ok=False, error="invalid_tool_call", content=f"Proxy rejected invalid tool call '{tool_call.name}'.")
                self.metrics["tool_execution_errors_total"] += 1
                self._log_tool_execution_result(session.request_id, tool_call, result)
                results.append(result)
                continue
            result = await self.tool_executor.execute(session, tool_call, payload)
            if not result.ok:
                self.metrics["tool_execution_errors_total"] += 1
            self._log_tool_execution_result(session.request_id, tool_call, result)
            results.append(result)
        return results

    async def _non_stream_orchestrated(self, payload: Dict[str, Any], session: SessionState, headers: Dict[str, str]) -> JSONResponse:
        current_payload = copy.deepcopy(rewrite_request_for_upstream(payload, session.policy))
        current_payload["stream"] = False
        last_tool_calls: List[ToolCall] = []
        last_tool_results: List[ToolExecutionResult] = []
        for iteration in range(session.policy.get("max_tool_iterations", MAX_TOOL_ITERATIONS) + 1):
            self._save_json_log(
                session.request_id,
                direction="forwarded",
                stage=f"non_stream_orchestrated_upstream_iteration_{iteration}",
                payload=current_payload,
                extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
            )
            response = await self.client.post(f"{self.lmstudio_base_url}/v1/chat/completions", json=current_payload, headers=headers)
            if response.status_code >= 400:
                self.metrics["upstream_errors_total"] += 1
                self._capture_failure(
                    session,
                    payload,
                    failure_type="BACKEND_ERROR_STATUS",
                    message=f"upstream error status {response.status_code}",
                )
                self.sessions.pop(session.request_id, None)
                return JSONResponse(status_code=response.status_code, content=safe_json_response(response))
            body = safe_json_response(response)
            choices = body.get("choices") or []
            if not choices:
                self._capture_failure(
                    session,
                    payload,
                    failure_type="EMPTY_UPSTREAM_BODY",
                    message="non-stream orchestrated response had no choices",
                )
                self.sessions.pop(session.request_id, None)
                return JSONResponse(status_code=response.status_code, content=body)
            message = choices[0].get("message") or {}
            content = message.get("content") if isinstance(message.get("content"), str) else ""
            detected_tool_calls = native_tool_calls_from_message(message)
            native_reasoning_content = message.get("reasoning_content") if isinstance(message.get("reasoning_content"), str) else ""
            non_structural_tool_block = False
            if native_reasoning_content:
                assistant_content = remove_control_tags(dedupe_reasoning_prefix(content, native_reasoning_content))
                assistant_reasoning = native_reasoning_content.strip()
            else:
                assistant_reasoning, assistant_content = normalize_assistant_resume_content(content)
            if not detected_tool_calls and "<tool_call>" in content:
                if not tool_call_open_is_structural_in_text(content):
                    non_structural_tool_block = True
                complete_tool = ToolCallParser.capture_complete_tool_call(content)
                if complete_tool and not tool_call_block_is_structural_in_text(content, complete_tool):
                    non_structural_tool_block = True
                if non_structural_tool_block:
                    self.sessions.pop(session.request_id, None)
                    return JSONResponse(status_code=response.status_code, content=body)
                if not complete_tool:
                    self.metrics["malformed_outputs_total"] += 1
                    repaired_tool_calls = await self._repair_tool_intent(current_payload, session, headers, content)
                    if repaired_tool_calls:
                        detected_tool_calls = repaired_tool_calls
                        assistant_reasoning, assistant_content = normalize_assistant_resume_content(content)
                    else:
                        self._capture_failure(
                            session,
                            payload,
                            failure_type="TOOL_CALL_INCOMPLETE",
                            message="model emitted an unfinished <tool_call> block",
                            visible_text=content,
                        )
                        self.sessions.pop(session.request_id, None)
                        return JSONResponse(content=build_text_chat_completion_response(payload, "Proxy stopped because the model emitted an unfinished <tool_call> block."))
                if not detected_tool_calls:
                    tool_call = ToolCallParser.parse_tool_call_xml(complete_tool)
                    if not tool_call:
                        self.metrics["malformed_outputs_total"] += 1
                        repaired_tool_calls = await self._repair_tool_intent(current_payload, session, headers, content)
                        if repaired_tool_calls:
                            detected_tool_calls = repaired_tool_calls
                            assistant_reasoning, assistant_content = normalize_assistant_resume_content(content)
                        else:
                            self._capture_failure(
                                session,
                                payload,
                                failure_type="TOOL_ARGUMENTS_INVALID_JSON",
                                message="model emitted a malformed <tool_call> block",
                                visible_text=content,
                            )
                            self.sessions.pop(session.request_id, None)
                            return JSONResponse(content=build_text_chat_completion_response(payload, "Proxy stopped because the model emitted a malformed <tool_call> block."))
                if not detected_tool_calls:
                    tool_call = ToolCallParser.sanitize_tool_arguments(tool_call)
                    tool_schema = ToolCallParser.tool_schema_from_openai_tools(session.policy.get("tools", []))
                    if not ToolCallParser.validate_tool_call(tool_call, tool_schema):
                        self.metrics["malformed_outputs_total"] += 1
                        repaired_tool_calls = await self._repair_tool_intent(current_payload, session, headers, content)
                        if repaired_tool_calls:
                            detected_tool_calls = repaired_tool_calls
                            assistant_reasoning, assistant_content = normalize_assistant_resume_content(content)
                        else:
                            self._capture_failure(
                                session,
                                payload,
                                failure_type="INVALID_OPENAI_CONTRACT",
                                message=f"proxy rejected invalid tool call '{tool_call.name}'",
                                visible_text=content,
                            )
                            self.sessions.pop(session.request_id, None)
                            return JSONResponse(content=build_text_chat_completion_response(payload, f"Proxy rejected invalid tool call '{tool_call.name}'.")) 
                if not detected_tool_calls:
                    detected_tool_calls = [tool_call]
                    assistant_reasoning, assistant_content = normalize_assistant_resume_content(content.replace(complete_tool, ""))
            if not detected_tool_calls:
                if not non_structural_tool_block:
                    repaired_tool_calls = await self._repair_tool_intent(current_payload, session, headers, content)
                    if repaired_tool_calls:
                        detected_tool_calls = repaired_tool_calls
                        assistant_reasoning, assistant_content = normalize_assistant_resume_content(content)
            if not detected_tool_calls:
                if iteration > 0 and last_tool_results and not content.strip():
                    self._capture_failure(
                        session,
                        payload,
                        failure_type="EMPTY_AFTER_THINKING_STRIP",
                        message="tool resume returned empty final answer",
                        visible_text=content,
                    )
                    self.sessions.pop(session.request_id, None)
                    return JSONResponse(content=build_text_chat_completion_response(payload, build_empty_resume_fallback(last_tool_calls, last_tool_results)))
                self.sessions.pop(session.request_id, None)
                return JSONResponse(status_code=response.status_code, content=body)
            if iteration >= session.policy.get("max_tool_iterations", MAX_TOOL_ITERATIONS):
                self.metrics["max_tool_iterations_total"] += 1
                self.sessions.pop(session.request_id, None)
                return JSONResponse(content=build_text_chat_completion_response(payload, "Proxy stopped after the maximum tool-call iterations."))
            self.metrics["tool_calls_parsed_total"] += len(detected_tool_calls)
            for tool_call in detected_tool_calls:
                self._log_tool_parse_result(session.request_id, tool_call)
            tool_results = await self._execute_tool_calls(session, payload, detected_tool_calls)
            last_tool_calls = detected_tool_calls
            last_tool_results = tool_results
            append_tool_results_to_payload(current_payload, assistant_content.strip(), assistant_reasoning, detected_tool_calls, tool_results)
            current_payload["stream"] = False
            self.metrics["resume_generations_total"] += 1
        self.metrics["max_tool_iterations_total"] += 1
        self.sessions.pop(session.request_id, None)
        return JSONResponse(content=build_text_chat_completion_response(payload, "Proxy stopped after the maximum tool-call iterations."))

    def _normalize_non_stream_response(self, body: Dict[str, Any], session: SessionState) -> None:
        choices = body.get("choices") or []
        if not choices:
            return
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or "<tool_call>" not in content:
            return
        if not tool_call_open_is_structural_in_text(content):
            return
        complete_tool = ToolCallParser.capture_complete_tool_call(content)
        if not complete_tool:
            self.metrics["malformed_outputs_total"] += 1
            return
        if not tool_call_block_is_structural_in_text(content, complete_tool):
            return
        tool_call = ToolCallParser.parse_tool_call_xml(complete_tool)
        if not tool_call:
            self.metrics["malformed_outputs_total"] += 1
            return
        tool_call = ToolCallParser.sanitize_tool_arguments(tool_call)
        tool_schema = ToolCallParser.tool_schema_from_openai_tools(session.policy.get("tools", []))
        if not ToolCallParser.validate_tool_call(tool_call, tool_schema):
            self.metrics["malformed_outputs_total"] += 1
            return
        reasoning_content, cleaned_content = normalize_assistant_resume_content(content.replace(complete_tool, ""))
        message["content"] = cleaned_content or None
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        client_tool_call = ToolCallParser.convert_to_openai_tool_call(tool_call)
        client_tool_call.pop("index", None)
        message["tool_calls"] = [client_tool_call]
        choices[0]["finish_reason"] = "tool_calls"
        self.metrics["tool_calls_parsed_total"] += 1
        self._log_tool_parse_result(session.request_id, tool_call)

    def _capture_enabled(self) -> bool:
        if not CAPTURE_FAILURES:
            return False
        if CAPTURE_SAMPLE_RATE <= 0:
            return False
        if CAPTURE_SAMPLE_RATE >= 1:
            return True
        return random.random() <= CAPTURE_SAMPLE_RATE

    def _observed_from_session(
        self,
        session: SessionState,
        *,
        response_log: Optional[Dict[str, Any]] = None,
        visible_text: str = "",
    ) -> Dict[str, Any]:
        final_visible_text = (visible_text or session.normalized_text_buffer or "")[:CAPTURE_MAX_CHARS]
        return {
            "visible_text": final_visible_text,
            "tool_call_count": len(session.tool_calls_captured),
            "has_done": bool((response_log or {}).get("done")),
            "empty_response": not final_visible_text.strip(),
            "thinking_leaked": "<think>" in final_visible_text or "</think>" in final_visible_text,
            "invalid_json": bool((response_log or {}).get("malformed_lines")),
            "incomplete_tool_call": session.current_state in {StreamState.TOOL_CAPTURE, StreamState.ERROR} or bool(session.tool_call_buffer),
        }

    def _raw_llama_chunks(self, session: SessionState, response_log: Optional[Dict[str, Any]] = None) -> List[str]:
        if not CAPTURE_RAW_CHUNKS:
            return []
        if response_log and response_log.get("chunks"):
            raw_chunks = [json.dumps(chunk, ensure_ascii=False, default=str) for chunk in response_log.get("chunks") or []]
        elif session.raw_text_buffer:
            raw_chunks = [session.raw_text_buffer]
        else:
            raw_chunks = []
        return [chunk[:CAPTURE_MAX_CHARS] for chunk in raw_chunks][-200:]

    def _capture_failure(
        self,
        session: SessionState,
        payload: Dict[str, Any],
        *,
        failure_type: str,
        message: str,
        exception: Optional[BaseException] = None,
        response_log: Optional[Dict[str, Any]] = None,
        visible_text: str = "",
        client_chunks: Optional[List[str]] = None,
    ) -> None:
        if not self._capture_enabled():
            return
        try:
            CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
            context = CaptureContext(
                request_id=session.request_id,
                payload=payload,
                mode="streaming" if payload.get("stream") else "non_streaming",
                model=str(payload.get("model") or "unknown"),
                llama_chunks=self._raw_llama_chunks(session, response_log=response_log),
                client_chunks=(client_chunks or [])[:200] if CAPTURE_CLIENT_CHUNKS else [],
                state_trace=list(session.events)[-200:],
                observed=self._observed_from_session(session, response_log=response_log, visible_text=visible_text),
            )
            capture_failure_sample(
                context,
                failure_type=failure_type,
                message=message,
                exception=exception,
                source="live_proxy",
            )
        except Exception:
            logger.exception("[%s] failure capture failed", session.request_id)

    def _capture_non_stream_contract_issues(self, session: SessionState, payload: Dict[str, Any], body: Dict[str, Any]) -> None:
        choices = body.get("choices") or []
        message = choices[0].get("message") if choices else {}
        content = message.get("content") if isinstance(message, dict) else ""
        validation = validate_non_stream_response(body)
        if not validation.ok:
            self._capture_failure(
                session,
                payload,
                failure_type="INVALID_OPENAI_CONTRACT",
                message="; ".join(validation.errors),
                visible_text=content if isinstance(content, str) else "",
            )
        elif isinstance(content, str) and ("<think>" in content or "</think>" in content):
            self._capture_failure(
                session,
                payload,
                failure_type="THINKING_LEAK",
                message="non-stream response leaked thinking tags",
                visible_text=content,
            )

    def _capture_stream_invariants(
        self,
        session: SessionState,
        payload: Dict[str, Any],
        response_log: Dict[str, Any],
        visible_text: str,
        client_chunks: Optional[List[str]] = None,
    ) -> None:
        if response_log.get("event_count", 0) == 0:
            self._capture_failure(
                session,
                payload,
                failure_type="EMPTY_UPSTREAM_BODY",
                message="stream returned no data events",
                response_log=response_log,
                visible_text=visible_text,
                client_chunks=client_chunks,
            )
            return
        if not response_log.get("done"):
            self._capture_failure(
                session,
                payload,
                failure_type="MISSING_DONE",
                message="stream ended before [DONE]",
                response_log=response_log,
                visible_text=visible_text,
                client_chunks=client_chunks,
            )
        observed = self._observed_from_session(session, response_log=response_log, visible_text=visible_text)
        if observed["invalid_json"]:
            self._capture_failure(
                session,
                payload,
                failure_type="INVALID_SSE_JSON",
                message="stream contained malformed SSE JSON",
                response_log=response_log,
                visible_text=visible_text,
                client_chunks=client_chunks,
            )
        if observed["thinking_leaked"]:
            self._capture_failure(
                session,
                payload,
                failure_type="THINKING_LEAK",
                message="client-bound stream leaked thinking tags",
                response_log=response_log,
                visible_text=visible_text,
                client_chunks=client_chunks,
            )
        if observed["incomplete_tool_call"]:
            self._capture_failure(
                session,
                payload,
                failure_type="TOOL_CALL_INCOMPLETE",
                message="stream ended with incomplete tool-call capture state",
                response_log=response_log,
                visible_text=visible_text,
                client_chunks=client_chunks,
            )
        if observed["empty_response"] and not observed["tool_call_count"] and observed["has_done"]:
            self._capture_failure(
                session,
                payload,
                failure_type="EMPTY_AFTER_THINKING_STRIP",
                message="stream produced no visible text and no tool calls",
                response_log=response_log,
                visible_text=visible_text,
                client_chunks=client_chunks,
            )

    def _capture_repair_issues(
        self,
        repair_session: SessionState,
        repair_payload: Dict[str, Any],
        response_log: Dict[str, Any],
        *,
        detected_tool_calls: List[ToolCall],
        valid_tool_calls: List[ToolCall],
    ) -> None:
        visible_text = repair_session.normalized_text_buffer
        if response_log.get("status_code") and int(response_log["status_code"]) >= 400:
            self._capture_failure(
                repair_session,
                repair_payload,
                failure_type="BACKEND_ERROR_STATUS",
                message=f"tool-intent repair upstream error status {response_log['status_code']}",
                response_log=response_log,
                visible_text=visible_text,
            )
            return
        if response_log.get("event_count", 0) == 0:
            self._capture_failure(
                repair_session,
                repair_payload,
                failure_type="EMPTY_UPSTREAM_BODY",
                message="tool-intent repair returned no data events",
                response_log=response_log,
                visible_text=visible_text,
            )
            return
        if response_log.get("malformed_lines"):
            self._capture_failure(
                repair_session,
                repair_payload,
                failure_type="INVALID_SSE_JSON",
                message="tool-intent repair stream contained malformed SSE JSON",
                response_log=response_log,
                visible_text=visible_text,
            )
        if not response_log.get("done") and not detected_tool_calls:
            self._capture_failure(
                repair_session,
                repair_payload,
                failure_type="MISSING_DONE",
                message="tool-intent repair stream ended before [DONE]",
                response_log=response_log,
                visible_text=visible_text,
            )
        if repair_session.current_state in {StreamState.TOOL_CAPTURE, StreamState.ERROR} or repair_session.tool_call_buffer:
            self._capture_failure(
                repair_session,
                repair_payload,
                failure_type="TOOL_CALL_INCOMPLETE",
                message="tool-intent repair ended with incomplete tool-call state",
                response_log=response_log,
                visible_text=visible_text,
            )
        if detected_tool_calls and not valid_tool_calls:
            self._capture_failure(
                repair_session,
                repair_payload,
                failure_type="INVALID_OPENAI_CONTRACT",
                message="tool-intent repair produced tool call(s) that failed schema validation",
                response_log=response_log,
                visible_text=visible_text,
            )
        if not detected_tool_calls and response_log.get("done") and not visible_text.strip():
            self._capture_failure(
                repair_session,
                repair_payload,
                failure_type="EMPTY_AFTER_THINKING_STRIP",
                message="tool-intent repair completed without visible text or tool calls",
                response_log=response_log,
                visible_text=visible_text,
            )

    async def _repair_tool_intent(self, payload: Dict[str, Any], session: SessionState, headers: Dict[str, str], assistant_text: str) -> List[ToolCall]:
        if not should_attempt_tool_intent_repair(payload, session, assistant_text):
            return []
        self.metrics["tool_intent_repairs_total"] += 1
        logger.info("[%s] attempting tool-intent repair generation", session.request_id)
        repair_payload = build_tool_intent_repair_payload(payload, session, assistant_text)
        self._save_json_log(
            session.request_id,
            direction="forwarded",
            stage="tool_intent_repair_upstream",
            payload=repair_payload,
            extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
        )
        repair_session = SessionState(request_id=f"{session.request_id}-repair")
        repair_session.policy = copy.deepcopy(session.policy)
        machine = StreamStateMachine(repair_session, repair_session.policy)
        detected_tool_calls: List[ToolCall] = []
        response_log = new_stream_response_log()
        try:
            async with self.client.stream("POST", f"{self.lmstudio_base_url}/v1/chat/completions", json=repair_payload, headers=headers) as response:
                response_log["status_code"] = response.status_code
                if response.status_code >= 400:
                    self.metrics["upstream_errors_total"] += 1
                    self.metrics["tool_intent_repair_failures_total"] += 1
                    response_log["error"] = "upstream error"
                    logger.warning("[%s] tool-intent repair upstream error status=%s", session.request_id, response.status_code)
                    return []
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    append_stream_response_line(response_log, line)
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        output = machine.flush()
                        if output.is_malformed:
                            self.metrics["malformed_outputs_total"] += 1
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("[%s] malformed repair SSE JSON: %r", session.request_id, data_str)
                        continue
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    finish_reason = choice.get("finish_reason")
                    native_tool_calls = delta.get("tool_calls")
                    if native_tool_calls:
                        append_native_tool_delta(repair_session, native_tool_calls)
                        if finish_reason == "tool_calls":
                            detected_tool_calls = consume_native_tool_calls(repair_session)
                            break
                        continue
                    if finish_reason == "tool_calls" and repair_session.native_tool_call_parts:
                        detected_tool_calls = consume_native_tool_calls(repair_session)
                        break
                    reasoning_delta = delta.get("reasoning_content") or ""
                    if reasoning_delta:
                        output = machine.advance_state(reasoning_delta)
                        if output.is_malformed:
                            self.metrics["malformed_outputs_total"] += 1
                            break
                        if output.tool_call:
                            detected_tool_calls = [output.tool_call]
                            break
                        continue
                    text_delta = delta.get("content") or ""
                    if not text_delta:
                        continue
                    output = machine.advance_state(text_delta)
                    if output.is_malformed:
                        self.metrics["malformed_outputs_total"] += 1
                        break
                    if output.tool_call:
                        detected_tool_calls = [output.tool_call]
                        break
        except Exception:
            self.metrics["tool_intent_repair_failures_total"] += 1
            response_log["error"] = "exception"
            logger.exception("[%s] tool-intent repair generation failed", session.request_id)
            return []
        finally:
            response_log["raw_text_buffer"] = repair_session.raw_text_buffer
            response_log["normalized_text_buffer"] = repair_session.normalized_text_buffer
            response_log["events"] = repair_session.events
            self._save_json_log(
                session.request_id,
                direction="upstream_response",
                stage="tool_intent_repair_response",
                payload=response_log,
                extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
            )
        if not detected_tool_calls and repair_session.native_tool_call_parts:
            detected_tool_calls = consume_native_tool_calls(repair_session)
        valid_tool_calls = validate_and_sanitize_tool_calls(detected_tool_calls, session.policy.get("tools", []))
        if valid_tool_calls:
            self.metrics["tool_intent_repair_success_total"] += 1
            logger.info("[%s] tool-intent repair produced %s tool call(s)", session.request_id, len(valid_tool_calls))
            return valid_tool_calls
        self._capture_repair_issues(
            repair_session,
            repair_payload,
            response_log,
            detected_tool_calls=detected_tool_calls,
            valid_tool_calls=valid_tool_calls,
        )
        self.metrics["tool_intent_repair_failures_total"] += 1
        logger.info("[%s] tool-intent repair produced no valid tool call", session.request_id)
        return []

    def _apply_tool_calls_to_non_stream_response(self, body: Dict[str, Any], session: SessionState, assistant_text: str, tool_calls: List[ToolCall]) -> None:
        choices = body.get("choices") or []
        if not choices:
            return
        message = choices[0].setdefault("message", {})
        message["role"] = message.get("role") or "assistant"
        reasoning_content, cleaned_content = normalize_assistant_resume_content(assistant_text)
        message["content"] = cleaned_content or None
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        client_tool_calls = []
        for index, tool_call in enumerate(tool_calls):
            client_tool_call = ToolCallParser.convert_to_openai_tool_call(tool_call, index=index)
            client_tool_call.pop("index", None)
            client_tool_calls.append(client_tool_call)
            self._log_tool_parse_result(session.request_id, tool_call)
        message["tool_calls"] = client_tool_calls
        choices[0]["finish_reason"] = "tool_calls"
        self.metrics["tool_calls_parsed_total"] += len(tool_calls)

    def _log_request(self, request_id: str, payload: Dict[str, Any], policy: Dict[str, Any]) -> None:
        logger.info(
            "[%s] request model=%s stream=%s tools=%s mode=%s requested_mode=%s intercept=%s pass_through=%s can_execute=%s",
            request_id,
            payload.get("model"),
            payload.get("stream"),
            len(payload.get("tools", [])),
            policy.get("proxy_mode"),
            policy.get("requested_proxy_mode"),
            policy.get("intercept_tools"),
            policy.get("pass_through"),
            policy.get("tool_execution_available"),
        )

    def _save_json_log(self, request_id: str, direction: str, stage: str, payload: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> None:
        if not self.enable_logging:
            return
        try:
            prune_result = self._prune_old_json_logs()
            PROXY_JSON_LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{stamp}_{safe_log_slug(direction, 20)}_{safe_log_slug(stage)}_{safe_log_slug(request_id, 32)}.json"
            record: Dict[str, Any] = {
                "time": datetime.now().isoformat(),
                "request_id": request_id,
                "direction": direction,
                "stage": stage,
                "retention_days": PROXY_JSON_LOG_RETENTION_DAYS,
                "payload": payload,
            }
            if extra:
                record["extra"] = extra
            if prune_result:
                record["prune"] = prune_result
            log_path = PROXY_JSON_LOG_DIR / filename
            log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            self.metrics["json_logs_saved_total"] += 1
        except Exception as exc:
            self.metrics["json_log_errors_total"] += 1
            logger.warning("[%s] failed to write proxy JSON log direction=%s stage=%s: %s", request_id, direction, stage, exc)

    def _save_stream_response_log(self, session: SessionState, stage: str, response_log: Dict[str, Any], assistant_text_parts: List[str]) -> None:
        response_log["assistant_text"] = "".join(assistant_text_parts)
        response_log["raw_text_buffer"] = session.raw_text_buffer
        response_log["normalized_text_buffer"] = session.normalized_text_buffer
        response_log["events"] = session.events
        self._save_json_log(
            session.request_id,
            direction="upstream_response",
            stage=stage,
            payload=response_log,
            extra={"url": f"{self.lmstudio_base_url}/v1/chat/completions"},
        )

    def _prune_old_json_logs(self, force: bool = False) -> Dict[str, Any]:
        import proxy.core_parts.config as config_module

        now = time.time()
        if not force and now - config_module.LAST_PROXY_JSON_LOG_PRUNE < PROXY_JSON_LOG_PRUNE_INTERVAL_SECONDS:
            return {"ok": True, "skipped": True, "deleted_count": 0}
        deleted_count = 0
        errors: List[str] = []
        try:
            PROXY_JSON_LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_root = PROXY_JSON_LOG_DIR.resolve()
            cutoff = now - (PROXY_JSON_LOG_RETENTION_DAYS * 24 * 60 * 60)
            for candidate in PROXY_JSON_LOG_DIR.glob("*.json"):
                try:
                    resolved = candidate.resolve()
                    resolved.relative_to(log_root)
                    if resolved.is_file() and resolved.stat().st_mtime < cutoff:
                        resolved.unlink()
                        deleted_count += 1
                except Exception as exc:
                    errors.append(f"{candidate.name}: {exc}")
        except Exception as exc:
            errors.append(str(exc))
        config_module.LAST_PROXY_JSON_LOG_PRUNE = now
        self.metrics["json_logs_pruned_total"] += deleted_count
        return {"ok": not errors, "skipped": False, "deleted_count": deleted_count, "errors": errors}

    def _log_tool_parse_result(self, request_id: str, tool_call: ToolCall) -> None:
        logger.info("[%s] tool parsed name=%s args=%s", request_id, tool_call.name, list(tool_call.arguments.keys()))

    def _log_tool_execution_result(self, request_id: str, tool_call: ToolCall, result: ToolExecutionResult) -> None:
        logger.info("[%s] tool executed name=%s ok=%s error=%s result_chars=%s", request_id, tool_call.name, result.ok, result.error, len(result.content))

    async def handle_healthcheck(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "lmstudio_base_url": self.lmstudio_base_url,
            "intercept_mode": self.intercept_mode,
            "default_proxy_mode": DEFAULT_PROXY_MODE,
            "tool_executor_configured": bool(TOOL_EXECUTOR_URL),
            "builtin_tools_enabled": ENABLE_BUILTIN_TOOLS,
            "builtin_execute_code_enabled": ENABLE_BUILTIN_EXECUTE_CODE,
            "tool_execution_available": tool_execution_available(),
            "upstream_tool_format": UPSTREAM_TOOL_FORMAT,
            "upstream_timeout_seconds": UPSTREAM_TIMEOUT_SECONDS,
            "upstream_connect_timeout_seconds": UPSTREAM_CONNECT_TIMEOUT_SECONDS,
            "resume_format": PROXY_RESUME_FORMAT,
            "xml_tool_response_role": XML_TOOL_RESPONSE_ROLE,
            "visible_reasoning": DEFAULT_VISIBLE_REASONING,
            "max_tool_iterations": MAX_TOOL_ITERATIONS,
            "tool_intent_repair_enabled": ENABLE_TOOL_INTENT_REPAIR,
            "max_tool_intent_repair_attempts": MAX_TOOL_INTENT_REPAIR_ATTEMPTS,
            "json_logs": {
                "directory": str(PROXY_JSON_LOG_DIR),
                "retention_days": PROXY_JSON_LOG_RETENTION_DAYS,
                "prune_interval_seconds": PROXY_JSON_LOG_PRUNE_INTERVAL_SECONDS,
            },
            "failure_capture": {
                "enabled": CAPTURE_FAILURES,
                "directory": str(CAPTURE_DIR),
                "raw_chunks": CAPTURE_RAW_CHUNKS,
                "client_chunks": CAPTURE_CLIENT_CHUNKS,
                "max_chars": CAPTURE_MAX_CHARS,
                "sample_rate": CAPTURE_SAMPLE_RATE,
            },
            "timestamp": datetime.now().isoformat(),
        }

    async def handle_metrics(self) -> Dict[str, Any]:
        return {**self.metrics, "active_sessions": len(self.sessions), "timestamp": datetime.now().isoformat()}
