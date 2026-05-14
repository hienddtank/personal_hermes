import copy
import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Request

from .config import (
    NATIVE_TOOL_REQUEST_FIELDS,
    PROXY_XML_TOOL_PROMPT_SENTINEL,
    UPSTREAM_TOOL_FORMAT,
)
from .models import ToolCall, ToolExecutionResult
from .parsing import ToolCallParser, parse_tool_arguments
from .payload_utils import (
    join_nonempty,
    render_tool_call_xml,
    render_tool_response_xml,
)


def rewrite_request_for_upstream(
    payload: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rewritten = {
        key: value
        for key, value in payload.items()
        if key != "proxy_mode" and not key.startswith("_proxy_")
    }
    tools = tools_for_proxy_prompt(rewritten, policy)
    use_proxy_xml_tools = should_use_proxy_xml_tools(policy) and bool(tools)
    if use_proxy_xml_tools:
        for field in NATIVE_TOOL_REQUEST_FIELDS:
            rewritten.pop(field, None)
    messages = rewritten.get("messages")
    if isinstance(messages, list):
        sanitized_messages = sanitize_messages_for_upstream(messages)
        if use_proxy_xml_tools:
            sanitized_messages = sanitize_proxy_xml_history_messages(sanitized_messages)
            sanitized_messages = inject_proxy_xml_tool_prompt(sanitized_messages, tools)
        rewritten["messages"] = sanitized_messages
    return rewritten


def should_use_proxy_xml_tools(policy: Optional[Dict[str, Any]]) -> bool:
    if not policy:
        return False
    if UPSTREAM_TOOL_FORMAT in {"native", "openai", "tool_calls"}:
        return False
    return bool(policy.get("intercept_tools") and not policy.get("pass_through"))


def tools_for_proxy_prompt(
    payload: Dict[str, Any],
    policy: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    tools = payload.get("tools")
    if isinstance(tools, list) and tools:
        return tools
    policy_tools = (policy or {}).get("tools")
    if isinstance(policy_tools, list):
        return policy_tools
    return []


def inject_proxy_xml_tool_prompt(
    messages: List[Any],
    tools: List[Dict[str, Any]],
) -> List[Any]:
    if message_list_contains_text(messages, PROXY_XML_TOOL_PROMPT_SENTINEL):
        return messages
    tool_prompt = build_proxy_xml_tool_prompt(tools)
    injected: List[Any] = []
    inserted = False
    for message in messages:
        if (
            not inserted
            and isinstance(message, dict)
            and str(message.get("role") or "") == "system"
            and isinstance(message.get("content"), str)
        ):
            updated = dict(message)
            updated["content"] = join_nonempty(str(message.get("content") or ""), tool_prompt)
            injected.append(updated)
            inserted = True
            continue
        injected.append(message)
    if inserted:
        return injected
    return [{"role": "system", "content": tool_prompt}, *injected]


def message_list_contains_text(messages: List[Any], needle: str) -> bool:
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and needle in content:
            return True
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and needle in str(part.get("text") or ""):
                    return True
    return False


def build_proxy_xml_tool_prompt(tools: List[Dict[str, Any]]) -> str:
    tool_specs = []
    for tool in tools or []:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            continue
        function = tool.get("function") or {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        description = str(function.get("description") or "").strip()
        parameters = function.get("parameters") or {"type": "object", "properties": {}}
        try:
            parameter_text = json.dumps(
                parameters,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        except TypeError:
            parameter_text = str(parameters)
        if description:
            tool_specs.append(f"- {name}: {description}\n  parameters: {parameter_text}")
        else:
            tool_specs.append(f"- {name}\n  parameters: {parameter_text}")
    available_tools = "\n".join(tool_specs) if tool_specs else "- none"
    return (
        f"{PROXY_XML_TOOL_PROMPT_SENTINEL}\n"
        "Native OpenAI tool calling is disabled for this upstream server request. "
        "If a tool is needed, emit exactly one XML tool call and then stop.\n"
        "Use this exact shape:\n"
        "<tool_call>\n"
        '{"name":"tool_name","arguments":{"parameter_name":"value"}}\n'
        "</tool_call>\n"
        "Use compact JSON inside the tag body. Keep any reasoning in <think>...</think> and put "
        "the tool call after the reasoning block. Do not emit OpenAI JSON tool_calls. "
        "If no tool is needed, answer normally.\n"
        "Available tools:\n"
        f"{available_tools}"
    )


def sanitize_proxy_xml_history_messages(messages: List[Any]) -> List[Any]:
    sanitized: List[Any] = []
    tool_call_names: Dict[str, str] = {}
    for message in messages:
        if not isinstance(message, dict):
            sanitized.append(message)
            continue
        role = str(message.get("role") or "")
        if role == "assistant" and message.get("tool_calls"):
            converted, names = convert_assistant_tool_calls_to_xml_message(message)
            tool_call_names.update(names)
            sanitized.append(converted)
            continue
        if role == "tool":
            sanitized.append(convert_tool_result_to_xml_user_message(message, tool_call_names))
            continue
        sanitized.append(message)
    return sanitized


def convert_assistant_tool_calls_to_xml_message(
    message: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, str]]:
    converted = {key: copy.deepcopy(value) for key, value in message.items() if key != "tool_calls"}
    tool_call_names: Dict[str, str] = {}
    rendered_calls = []
    for index, item in enumerate(message.get("tool_calls") or []):
        if not isinstance(item, dict):
            continue
        function = item.get("function") or {}
        name = str(function.get("name") or "").strip() or "unknown_tool"
        tool_call_id = str(item.get("id") or f"call_{index}")
        tool_call_names[tool_call_id] = name
        arguments = parse_tool_arguments(function.get("arguments") or "{}")
        rendered_calls.append(
            render_tool_call_xml(ToolCall(name=name, arguments=arguments, id=tool_call_id, source="history"))
        )
    content = converted.get("content")
    converted["content"] = join_nonempty(content if isinstance(content, str) else "", "\n".join(rendered_calls)) or None
    converted["role"] = "assistant"
    return converted, tool_call_names


def convert_tool_result_to_xml_user_message(
    message: Dict[str, Any],
    tool_call_names: Dict[str, str],
) -> Dict[str, Any]:
    import uuid

    tool_call_id = str(message.get("tool_call_id") or "")
    name = str(message.get("name") or tool_call_names.get(tool_call_id) or "unknown_tool")
    content = message.get("content")
    result = ToolExecutionResult(
        ok=True,
        content=content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str),
    )
    return {
        "role": "user",
        "content": render_tool_response_xml(
            ToolCall(
                name=name,
                arguments={},
                id=tool_call_id or f"call_{uuid.uuid4().hex[:12]}",
                source="history",
            ),
            result,
        ),
    }


def sanitize_messages_for_upstream(messages: List[Any]) -> List[Any]:
    sanitized: List[Any] = []
    for message in messages:
        if not isinstance(message, dict):
            sanitized.append(message)
            continue
        role = str(message.get("role") or "")
        content = message.get("content")
        if role != "system" and isinstance(content, str) and not content.strip():
            continue
        sanitized.append(message)
    return sanitized


def forward_headers(request: Request) -> Dict[str, str]:
    allowed = {"authorization", "openai-organization", "openai-project", "x-request-id"}
    headers = {name: value for name, value in request.headers.items() if name.lower() in allowed}
    headers["Content-Type"] = "application/json"
    return headers


def safe_json_response(response: httpx.Response) -> Dict[str, Any]:
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            return parsed
        return {"data": parsed}
    except Exception:
        return {
            "error": "non-json upstream response",
            "status_code": response.status_code,
            "body": response.text,
        }


def sse_data(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"


def chunk_base_from(chunk: Dict[str, Any]) -> Dict[str, Any]:
    choice = (chunk.get("choices") or [{"index": 0}])[0]
    return {
        "id": chunk.get("id", "chatcmpl-compat"),
        "object": chunk.get("object", "chat.completion.chunk"),
        "created": chunk.get("created"),
        "model": chunk.get("model", ""),
        "choices": [{"index": choice.get("index", 0)}],
    }


def content_chunk_from(chunk: Dict[str, Any], text_delta: str) -> Dict[str, Any]:
    out = chunk_base_from(chunk)
    out["choices"][0]["delta"] = {"content": text_delta}
    out["choices"][0]["finish_reason"] = None
    return out


def tool_call_chunk_from(chunk: Dict[str, Any], tool_call: Dict[str, Any]) -> Dict[str, Any]:
    out = chunk_base_from(chunk)
    out["choices"][0]["delta"] = {"tool_calls": [tool_call]}
    out["choices"][0]["finish_reason"] = None
    return out


def finish_chunk_from(chunk: Dict[str, Any], finish_reason: str) -> Dict[str, Any]:
    out = chunk_base_from(chunk)
    out["choices"][0]["delta"] = {}
    out["choices"][0]["finish_reason"] = finish_reason
    return out
