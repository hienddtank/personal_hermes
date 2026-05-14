import json
import re
import uuid
from typing import Any, Dict, List, Optional

from .models import SessionState, ToolCall


def normalize_json_like_text(text: str) -> str:
    normalized: List[str] = []
    in_string = False
    escaped = False
    for char in text:
        if escaped:
            normalized.append(char)
            escaped = False
            continue
        if char == "\\":
            normalized.append(char)
            escaped = True
            continue
        if char == '"':
            normalized.append(char)
            in_string = not in_string
            continue
        if in_string and char == "\n":
            normalized.append("\\n")
            continue
        if in_string and char == "\r":
            normalized.append("\\r")
            continue
        normalized.append(char)
    return "".join(normalized)


def parse_tool_arguments(arguments: Any) -> Dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        return {"value": arguments}
    try:
        parsed = json.loads(normalize_json_like_text(arguments))
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    except json.JSONDecodeError:
        return {"_raw": arguments}


class ToolCallParser:
    @staticmethod
    def detect_think_open(buffer: str) -> bool:
        return "<think>" in buffer

    @staticmethod
    def detect_think_close(buffer: str) -> bool:
        return "</think>" in buffer

    @staticmethod
    def detect_tool_call_open(buffer: str) -> bool:
        return "<tool_call>" in buffer

    @staticmethod
    def detect_tool_call_close(buffer: str) -> bool:
        return "</tool_call>" in buffer

    @staticmethod
    def capture_complete_tool_call(buffer: str) -> Optional[str]:
        start = buffer.find("<tool_call>")
        end = buffer.find("</tool_call>", start + len("<tool_call>"))
        if start != -1 and end != -1:
            return buffer[start : end + len("</tool_call>")]
        return None

    @staticmethod
    def extract_tool_call_body(text: str) -> Optional[str]:
        complete_tool = ToolCallParser.capture_complete_tool_call(text)
        if not complete_tool:
            return None
        start = complete_tool.find("<tool_call>") + len("<tool_call>")
        end = complete_tool.rfind("</tool_call>")
        return complete_tool[start:end]

    @staticmethod
    def parse_tool_call_json(body: str) -> Optional[ToolCall]:
        candidate = body.strip()
        candidate = re.sub(r"^```(?:json)?\s*\n?", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\n?```$", "", candidate)
        if not candidate:
            return None
        try:
            payload = json.loads(normalize_json_like_text(candidate))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        function_payload = payload.get("function") if isinstance(payload.get("function"), dict) else None
        name = str(payload.get("name") or (function_payload or {}).get("name") or "").strip()
        if not name:
            return None
        arguments = payload.get("arguments")
        if arguments is None and function_payload is not None:
            arguments = function_payload.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = parse_tool_arguments(arguments)
        return ToolCall(name=name, arguments=arguments)

    @staticmethod
    def parse_tool_call_xml(text: str) -> Optional[ToolCall]:
        try:
            function_match = re.search(r"<function=([^>]+)>", text)
            if not function_match:
                body = ToolCallParser.extract_tool_call_body(text)
                if body is None:
                    return None
                return ToolCallParser.parse_tool_call_json(body)
            function_name = function_match.group(1).strip()
            arguments: Dict[str, Any] = {}
            parameter_pattern = r"<parameter=([^>]+)>(.*?)</parameter>"
            for param_match in re.finditer(parameter_pattern, text, re.DOTALL):
                param_name = param_match.group(1).strip()
                param_value = param_match.group(2).strip()
                arguments[param_name] = param_value
            return ToolCall(name=function_name, arguments=arguments)
        except Exception:
            return None

    @staticmethod
    def sanitize_tool_arguments(tool_call: ToolCall) -> ToolCall:
        sanitized_args: Dict[str, Any] = {}
        for key, value in tool_call.arguments.items():
            if isinstance(value, str):
                value = value.strip()
                value = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n", "", value)
                value = re.sub(r"\n```$", "", value)
            sanitized_args[key] = value
        return ToolCall(
            name=tool_call.name,
            arguments=sanitized_args,
            id=tool_call.id,
            source=tool_call.source,
        )

    @staticmethod
    def tool_schema_from_openai_tools(tools: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        schema: Dict[str, Dict[str, Any]] = {}
        for tool in tools or []:
            if tool.get("type") != "function":
                continue
            function = tool.get("function") or {}
            name = function.get("name")
            if not name:
                continue
            parameters = function.get("parameters") or {}
            schema[name] = {
                "required": parameters.get("required", []),
                "parameters": parameters,
            }
        return schema

    @staticmethod
    def validate_tool_call(tool_call: ToolCall, tool_schema: Dict[str, Dict[str, Any]]) -> bool:
        if not tool_call.name:
            return False
        if not tool_schema:
            return True
        if tool_call.name not in tool_schema:
            return False
        required = tool_schema[tool_call.name].get("required", [])
        return all(param in tool_call.arguments for param in required)

    @staticmethod
    def convert_to_openai_tool_call(tool_call: ToolCall, index: int = 0) -> Dict[str, Any]:
        return {
            "index": index,
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.name,
                "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
            },
        }


def append_native_tool_delta(session: SessionState, tool_deltas: List[Dict[str, Any]]) -> None:
    for tool_delta in tool_deltas:
        index = int(tool_delta.get("index", 0))
        part = session.native_tool_call_parts.setdefault(
            index,
            {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            },
        )
        if tool_delta.get("id"):
            part["id"] = tool_delta["id"]
        if tool_delta.get("type"):
            part["type"] = tool_delta["type"]
        function_delta = tool_delta.get("function") or {}
        if function_delta.get("name"):
            part["function"]["name"] += str(function_delta["name"])
        if function_delta.get("arguments"):
            part["function"]["arguments"] += str(function_delta["arguments"])


def consume_native_tool_calls(session: SessionState) -> List[ToolCall]:
    tool_calls: List[ToolCall] = []
    for index in sorted(session.native_tool_call_parts):
        part = session.native_tool_call_parts[index]
        function = part.get("function") or {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        arguments = parse_tool_arguments(function.get("arguments") or "{}")
        tool_calls.append(
            ToolCall(
                name=name,
                arguments=arguments,
                id=part.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                source="native",
            )
        )
    session.native_tool_call_parts = {}
    return tool_calls


def native_tool_calls_from_message(message: Dict[str, Any]) -> List[ToolCall]:
    tool_calls: List[ToolCall] = []
    for index, item in enumerate(message.get("tool_calls") or []):
        function = item.get("function") or {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        arguments = parse_tool_arguments(function.get("arguments") or "{}")
        tool_calls.append(
            ToolCall(
                name=name,
                arguments=arguments,
                id=item.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                source="native",
            )
        )
    return tool_calls
