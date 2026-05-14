import asyncio
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx

from .config import (
    ENABLE_BUILTIN_EXECUTE_CODE,
    ENABLE_BUILTIN_TOOLS,
    MAX_TOOL_RESULT_CHARS,
    TOOL_EXECUTOR_API_KEY,
    TOOL_EXECUTOR_TIMEOUT,
    TOOL_EXECUTOR_URL,
    logger,
)
from .models import SessionState, ToolCall, ToolExecutionResult
from .payload_utils import tool_call_to_message_dict, tool_signature, truncate_text


async def run_builtin_execute_code(code: str) -> ToolExecutionResult:
    if not code.strip():
        return ToolExecutionResult(
            ok=False,
            error="empty_code",
            content="execute_code was called with an empty code argument.",
        )
    with tempfile.TemporaryDirectory(prefix="proxy_execute_code_") as temp_dir:
        script_path = Path(temp_dir) / "tool_code.py"
        script_path.write_text(code, encoding="utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                cwd=temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TOOL_EXECUTOR_TIMEOUT)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolExecutionResult(
                    ok=False,
                    error="timeout",
                    content=f"execute_code timed out after {TOOL_EXECUTOR_TIMEOUT} seconds.",
                )
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            content = {
                "exit_code": proc.returncode,
                "stdout": truncate_text(stdout_text, MAX_TOOL_RESULT_CHARS),
                "stderr": truncate_text(stderr_text, MAX_TOOL_RESULT_CHARS),
            }
            return ToolExecutionResult(
                ok=proc.returncode == 0,
                error=None if proc.returncode == 0 else "nonzero_exit",
                content=json.dumps(content, ensure_ascii=False),
                data=content,
            )
        except Exception as exc:
            return ToolExecutionResult(ok=False, error=type(exc).__name__, content=f"execute_code failed: {exc}")


class ToolExecutor:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def execute(
        self,
        session: SessionState,
        tool_call: ToolCall,
        payload: Dict[str, Any],
    ) -> ToolExecutionResult:
        signature = tool_signature(tool_call)
        if signature in session.executed_tool_signatures:
            return ToolExecutionResult(
                ok=False,
                error="duplicate_tool_call",
                content=(
                    "Duplicate tool call suppressed by proxy idempotency guard. "
                    "If this was intentional, call the tool with distinct arguments."
                ),
            )
        session.executed_tool_signatures.add(signature)
        if TOOL_EXECUTOR_URL:
            return await self._execute_via_http(session, tool_call, payload)
        if ENABLE_BUILTIN_TOOLS:
            return await self._execute_builtin(tool_call)
        return ToolExecutionResult(
            ok=False,
            error="tool_executor_not_configured",
            content=(
                "Tool execution is not configured in the proxy. Set "
                "PROXY_TOOL_EXECUTOR_URL to an HTTP executor, or enable limited "
                "built-in tools with PROXY_ENABLE_BUILTIN_TOOLS=true."
            ),
        )

    async def _execute_via_http(
        self,
        session: SessionState,
        tool_call: ToolCall,
        payload: Dict[str, Any],
    ) -> ToolExecutionResult:
        headers = {"Content-Type": "application/json"}
        if TOOL_EXECUTOR_API_KEY:
            headers["Authorization"] = f"Bearer {TOOL_EXECUTOR_API_KEY}"
        request_body = {
            "request_id": session.request_id,
            "tool_call_id": tool_call.id,
            "name": tool_call.name,
            "arguments": tool_call.arguments,
            "tool_call": tool_call_to_message_dict(tool_call),
            "model": payload.get("model"),
        }
        try:
            response = await self.client.post(
                TOOL_EXECUTOR_URL,
                json=request_body,
                headers=headers,
                timeout=TOOL_EXECUTOR_TIMEOUT,
            )
            if response.status_code >= 400:
                return ToolExecutionResult(
                    ok=False,
                    error=f"http_{response.status_code}",
                    content=truncate_text(response.text, MAX_TOOL_RESULT_CHARS),
                )
            try:
                data = response.json()
            except Exception:
                return ToolExecutionResult(ok=True, content=truncate_text(response.text, MAX_TOOL_RESULT_CHARS))
            content = data.get("content") if isinstance(data, dict) else None
            if content is None and isinstance(data, dict):
                content = data.get("result", data.get("output", data))
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            return ToolExecutionResult(
                ok=bool(data.get("ok", True)) if isinstance(data, dict) else True,
                content=truncate_text(content, MAX_TOOL_RESULT_CHARS),
                error=data.get("error") if isinstance(data, dict) else None,
                data=data,
            )
        except Exception as exc:
            logger.exception("[%s] tool executor HTTP call failed", session.request_id)
            return ToolExecutionResult(ok=False, error=type(exc).__name__, content=f"Tool executor failed: {exc}")

    async def _execute_builtin(self, tool_call: ToolCall) -> ToolExecutionResult:
        if tool_call.name == "echo":
            return ToolExecutionResult(ok=True, content=json.dumps(tool_call.arguments, ensure_ascii=False), data=tool_call.arguments)
        if tool_call.name in {"get_time", "now"}:
            data = {"timestamp": datetime.now().isoformat()}
            return ToolExecutionResult(ok=True, content=json.dumps(data, ensure_ascii=False), data=data)
        if tool_call.name == "execute_code" and ENABLE_BUILTIN_EXECUTE_CODE:
            return await run_builtin_execute_code(str(tool_call.arguments.get("code", "")))
        return ToolExecutionResult(
            ok=False,
            error="unknown_builtin_tool",
            content=(
                f"No built-in proxy executor is available for tool '{tool_call.name}'. "
                "Use PROXY_TOOL_EXECUTOR_URL for the full Hermes toolset."
            ),
        )
