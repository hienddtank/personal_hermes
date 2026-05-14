import copy
import json
import time
from typing import Any, Dict, List

from .config import (
    ENABLE_BUILTIN_TOOLS,
    ENABLE_TOOL_INTENT_REPAIR,
    MAX_TOOL_INTENT_REPAIR_ATTEMPTS,
    MAX_TOOL_RESULT_CHARS,
    PROXY_RESUME_FORMAT,
    TOOL_EXECUTOR_URL,
    TOOL_INTENT_REPAIR_CONTEXT_CHARS,
    TOOL_INTENT_REPAIR_MAX_TOKENS,
    UPSTREAM_TOOL_FORMAT,
    XML_TOOL_RESPONSE_ROLE,
)
from .models import SessionState, StreamState, ToolCall, ToolExecutionResult
from .parsing import ToolCallParser
from .text_utils import remove_control_tags


def normalize_lmstudio_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    return normalized


def safe_log_slug(value: str, max_length: int = 80) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in value)
    slug = "_".join(part for part in cleaned.split("_") if part)
    return slug[:max_length] or "unknown"


def new_stream_response_log() -> Dict[str, Any]:
    return {
        "status_code": None,
        "event_count": 0,
        "done": False,
        "finish_reasons": [],
        "chunks": [],
        "malformed_lines": [],
    }


def append_stream_response_line(response_log: Dict[str, Any], line: str) -> None:
    data_str = line[6:] if line.startswith("data: ") else line
    response_log["event_count"] = int(response_log.get("event_count", 0)) + 1
    if data_str.strip() == "[DONE]":
        response_log["done"] = True
        response_log["chunks"].append({"done": True})
        return
    try:
        chunk = json.loads(data_str)
    except json.JSONDecodeError:
        response_log["malformed_lines"].append(data_str)
        response_log["chunks"].append({"raw": data_str})
        return
    choice = (chunk.get("choices") or [{}])[0]
    finish_reason = choice.get("finish_reason")
    if finish_reason:
        response_log["finish_reasons"].append(finish_reason)
    response_log["chunks"].append(chunk)


def tool_execution_available() -> bool:
    return bool(TOOL_EXECUTOR_URL) or ENABLE_BUILTIN_TOOLS


def should_attempt_tool_intent_repair(
    payload: Dict[str, Any],
    session: SessionState,
    assistant_text: str,
) -> bool:
    if not ENABLE_TOOL_INTENT_REPAIR or MAX_TOOL_INTENT_REPAIR_ATTEMPTS <= 0:
        return False
    if not session.policy.get("intercept_tools") or not session.policy.get("has_tools"):
        return False
    attempts = int(payload.get("_proxy_tool_intent_repair_attempts", 0) or 0)
    if attempts >= MAX_TOOL_INTENT_REPAIR_ATTEMPTS:
        return False
    return looks_like_tool_intent(assistant_text)


def looks_like_tool_intent(text: str) -> bool:
    import re

    normalized = " ".join((text or "").strip().split())
    if not normalized:
        return False
    patterns = (
        r"<tool_call\b",
        r"<function=",
        r"\bcalling\s+(the\s+)?[a-z_][a-z0-9_-]*\s+tool\b",
        r"\bcall(?:ing)?\s+(the\s+)?[a-z_][a-z0-9_-]*\s+tool\b",
        r"\b(let me|i(?:'ll| will| need to| should| can| have to)|going to)\s+"
        r"(use|call|run|invoke|execute|try calling)\b",
        r"\b(let me|i(?:'ll| will| need to| should| can| have to)|going to)\s+"
        r"(check|inspect|read|search|list|look at|look for)\b.+"
        r"\b(skill|file|folder|directory|workspace|repo|repository|endpoint|api|tool|terminal|shell|command)\b",
        r"\b(use|call|invoke|execute|run)\s+(the\s+)?"
        r"(tool|terminal|shell|command|codex|codex forward)\b",
        r"\bcalling\s+(the\s+)?"
        r"(tool|terminal|shell|command|codex|codex forward)\b",
        r"\b(terminal|shell|command)\s*:",
        r"\b(curl|powershell|cmd(?:\.exe)?|python|node|npm|git)\b.+"
        r"\b(http://|https://|/run|/v1/|host\.docker\.internal)\b",
        r"\b(post|get|put|patch|delete)\s+(/[A-Za-z0-9_./-]+|https?://)",
        r"\bcodex[- ]forward\b",
        r"\blocal_forwarder\b",
    )
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)


def tool_names_from_openai_tools(tools: List[Dict[str, Any]]) -> List[str]:
    names = []
    for tool in tools or []:
        if tool.get("type") != "function":
            continue
        name = (tool.get("function") or {}).get("name")
        if name:
            names.append(str(name))
    return names


def build_tool_intent_repair_prompt(tools: List[Dict[str, Any]]) -> str:
    names = tool_names_from_openai_tools(tools)
    name_hint = f"\nAvailable tool names: {', '.join(names)}\n" if names else "\n"
    return (
        "Your previous assistant turn said a tool should be used, but it ended without "
        "emitting the required tool call.\n"
        f"{name_hint}"
        "If a tool is needed, reply ONLY with one valid XML tool call in this exact shape:\n"
        "<tool_call>\n"
        "<function=tool_name>\n"
        "<parameter=parameter_name>\n"
        "parameter value\n"
        "</parameter>\n"
        "</function>\n"
        "</tool_call>\n\n"
        "Do not include prose, markdown, analysis, or any text before or after the XML. "
        "If no tool is needed, reply only: NO_TOOL_NEEDED"
    )


def validate_and_sanitize_tool_calls(
    tool_calls: List[ToolCall],
    tools: List[Dict[str, Any]],
) -> List[ToolCall]:
    tool_schema = ToolCallParser.tool_schema_from_openai_tools(tools)
    valid_tool_calls: List[ToolCall] = []
    for tool_call in tool_calls:
        sanitized = ToolCallParser.sanitize_tool_arguments(tool_call)
        if ToolCallParser.validate_tool_call(sanitized, tool_schema):
            valid_tool_calls.append(sanitized)
    return valid_tool_calls


def build_repair_source_text(assistant_text_parts: List[str], raw_text: str) -> str:
    visible_text = "".join(assistant_text_parts)
    if raw_text.strip() and raw_text.strip() != visible_text.strip():
        return join_nonempty(visible_text, tail_text(raw_text, TOOL_INTENT_REPAIR_CONTEXT_CHARS))
    if "<tool_call" in raw_text and "<tool_call" not in visible_text:
        return join_nonempty(visible_text, tail_text(raw_text, TOOL_INTENT_REPAIR_CONTEXT_CHARS))
    if not visible_text.strip() and raw_text.strip():
        return tail_text(raw_text, TOOL_INTENT_REPAIR_CONTEXT_CHARS)
    return visible_text


def tail_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"...[earlier text omitted]\n{text[-max_chars:]}"


def response_has_tool_calls(body: Dict[str, Any]) -> bool:
    choices = body.get("choices") or []
    if not choices:
        return False
    message = choices[0].get("message") or {}
    return bool(message.get("tool_calls"))


def response_assistant_text(body: Dict[str, Any]) -> str:
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else ""


def reset_session_turn_state(session: SessionState) -> None:
    session.current_state = StreamState.PASS_THROUGH
    session.pending_text = ""
    session.raw_text_buffer = ""
    session.normalized_text_buffer = ""
    session.reasoning_buffer = ""
    session.tool_call_buffer = ""
    session.visible_xml_buffer = ""
    session.hidden_xml_closer = None
    session.native_tool_call_parts = {}


def tool_signature(tool_call: ToolCall) -> str:
    return json.dumps(
        {"name": tool_call.name, "arguments": tool_call.arguments},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"


def tool_call_to_message_dict(tool_call: ToolCall, index: int = 0) -> Dict[str, Any]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": copy.deepcopy(tool_call.arguments),
        },
    }


def format_tool_result_content(result: ToolExecutionResult) -> str:
    if result.ok:
        return truncate_text(result.content, MAX_TOOL_RESULT_CHARS)
    return json.dumps(
        {
            "ok": False,
            "error": result.error,
            "content": truncate_text(result.content, MAX_TOOL_RESULT_CHARS),
        },
        ensure_ascii=False,
    )


def split_reasoning_content(text: str) -> tuple[str, str]:
    if not isinstance(text, str) or not text:
        return "", ""
    think_open = text.find("<think>")
    think_close = text.find("</think>")
    if think_open == -1 or think_close == -1 or think_close < think_open:
        return "", text.strip()
    reasoning = text[think_open + len("<think>") : think_close].strip()
    content = join_nonempty(text[:think_open].strip(), text[think_close + len("</think>") :].strip())
    return reasoning, content


def dedupe_reasoning_prefix(content: str, reasoning: str) -> str:
    content = content.strip()
    reasoning = reasoning.strip()
    if reasoning and content.startswith(reasoning):
        return content[len(reasoning) :].lstrip()
    return content


def normalize_assistant_resume_content(text: str) -> tuple[str, str]:
    reasoning, content = split_reasoning_content(text)
    content = dedupe_reasoning_prefix(remove_control_tags(content), reasoning)
    return reasoning, content


def append_tool_results_to_payload(
    payload: Dict[str, Any],
    assistant_content: str,
    reasoning_content: str,
    tool_calls: List[ToolCall],
    tool_results: List[ToolExecutionResult],
) -> None:
    messages = list(payload.get("messages") or [])
    reasoning_content = reasoning_content.strip() if isinstance(reasoning_content, str) else ""
    resume_format = choose_resume_format(tool_calls)
    if resume_format == "xml":
        assistant_message: Dict[str, Any] = {
            "role": "assistant",
            "content": join_nonempty(
                assistant_content,
                "\n".join(render_tool_call_xml(tool_call) for tool_call in tool_calls),
            ),
        }
        if reasoning_content:
            assistant_message["reasoning_content"] = reasoning_content
        messages.append(assistant_message)
        for tool_call, result in zip(tool_calls, tool_results):
            role = XML_TOOL_RESPONSE_ROLE if XML_TOOL_RESPONSE_ROLE in {"user", "tool"} else "user"
            tool_message: Dict[str, Any] = {"role": role, "content": render_tool_response_xml(tool_call, result)}
            if role == "tool":
                tool_message["tool_call_id"] = tool_call.id
                tool_message["name"] = tool_call.name
            messages.append(tool_message)
        payload["messages"] = messages
        payload["stream"] = True
        return

    assistant_message: Dict[str, Any] = {
        "role": "assistant",
        "content": assistant_content or None,
        "tool_calls": [
            tool_call_to_message_dict(tool_call, index=index)
            for index, tool_call in enumerate(tool_calls)
        ],
    }
    if reasoning_content:
        assistant_message["reasoning_content"] = reasoning_content
    messages.append(assistant_message)
    for tool_call, result in zip(tool_calls, tool_results):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.name,
                "content": format_tool_result_content(result),
            }
        )
    payload["messages"] = messages
    payload["stream"] = True


def choose_resume_format(tool_calls: List[ToolCall]) -> str:
    if PROXY_RESUME_FORMAT in {"xml", "openai"}:
        return PROXY_RESUME_FORMAT
    if UPSTREAM_TOOL_FORMAT not in {"native", "openai", "tool_calls"}:
        return "xml"
    return "openai"


def join_nonempty(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


def render_tool_call_xml(tool_call: ToolCall) -> str:
    payload = {"name": tool_call.name, "arguments": tool_call.arguments}
    return "\n".join(
        ["<tool_call>", json.dumps(payload, ensure_ascii=False, separators=(",", ":")), "</tool_call>"]
    )


def render_tool_response_xml(tool_call: ToolCall, result: ToolExecutionResult) -> str:
    return "\n".join(
        [
            "<tool_response>",
            f"<function={tool_call.name}>",
            "<result>",
            format_tool_result_content(result),
            "</result>",
            "</function>",
            "</tool_response>",
        ]
    )


def build_text_chat_completion_response(payload: Dict[str, Any], content: str) -> Dict[str, Any]:
    import uuid

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.get("model", ""),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def build_empty_resume_fallback(
    tool_calls: List[ToolCall],
    tool_results: List[ToolExecutionResult],
) -> str:
    lines = [
        "The tool call completed, but the model returned an empty final answer.",
        "",
        "Tool results:",
    ]
    for tool_call, result in zip(tool_calls, tool_results):
        status = "ok" if result.ok else f"error: {result.error or 'unknown'}"
        lines.extend([f"- {tool_call.name}: {status}", truncate_text(result.content, 2000)])
    return "\n".join(lines)
