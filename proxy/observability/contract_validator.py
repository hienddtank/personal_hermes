import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)


def _has_thinking_text(value: Any) -> bool:
    return isinstance(value, str) and ("<think>" in value or "</think>" in value)


def validate_non_stream_response(body: Dict[str, Any]) -> ValidationResult:
    errors: List[str] = []
    if not isinstance(body, dict):
        return ValidationResult(False, ["response must be an object"])
    if not body.get("object"):
        errors.append("missing object")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        errors.append("missing choices")
        return ValidationResult(False, errors)
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        errors.append("missing message")
    else:
        role = message.get("role")
        if role not in {"assistant", "tool"}:
            errors.append("invalid message.role")
        content = message.get("content")
        if _has_thinking_text(content):
            errors.append("thinking leaked in content")
        tool_calls = message.get("tool_calls")
        if tool_calls is not None:
            if not isinstance(tool_calls, list):
                errors.append("tool_calls must be a list")
            else:
                for item in tool_calls:
                    if item.get("type") != "function":
                        errors.append("tool_call type must be function")
                        continue
                    function = item.get("function")
                    if not isinstance(function, dict):
                        errors.append("tool_call missing function")
                        continue
                    if not function.get("name"):
                        errors.append("tool_call missing function.name")
                    if "arguments" not in function:
                        errors.append("tool_call missing function.arguments")
    if "finish_reason" not in choice:
        errors.append("missing finish_reason")
    usage = body.get("usage")
    if usage is not None and not isinstance(usage, dict):
        errors.append("usage must be an object")
    return ValidationResult(not errors, errors)


def validate_sse_events(events: Iterable[str]) -> ValidationResult:
    errors: List[str] = []
    done_seen = False
    for raw_event in events:
        if not raw_event.startswith("data:"):
            errors.append("event must start with data:")
            continue
        payload = raw_event[5:].strip()
        if payload == "[DONE]":
            done_seen = True
            continue
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            errors.append("invalid SSE JSON")
            continue
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            errors.append("chunk missing choices")
            continue
        delta = (choices[0] or {}).get("delta") or {}
        if _has_thinking_text(delta.get("content")) or _has_thinking_text(delta.get("reasoning_content")):
            errors.append("thinking leaked in stream")
        tool_calls = delta.get("tool_calls")
        if tool_calls is not None and not isinstance(tool_calls, list):
            errors.append("tool_calls delta must be a list")
    if not done_seen:
        errors.append("missing [DONE]")
    return ValidationResult(not errors, errors)

