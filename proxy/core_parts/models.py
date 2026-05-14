import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class StreamState(str, Enum):
    PASS_THROUGH = "pass_through"
    THINKING = "thinking"
    TOOL_CAPTURE = "tool_capture"
    WAIT_TOOL_RESULT = "wait_tool_result"
    RESUME = "resume"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    source: str = "xml"


@dataclass
class ToolExecutionResult:
    ok: bool
    content: str
    error: Optional[str] = None
    data: Any = None


@dataclass
class ParsedOutput:
    state: StreamState
    text_delta: str = ""
    tool_call: Optional[ToolCall] = None
    is_malformed: bool = False


@dataclass
class SessionState:
    request_id: str
    current_state: StreamState = StreamState.PASS_THROUGH
    pending_text: str = ""
    raw_text_buffer: str = ""
    normalized_text_buffer: str = ""
    reasoning_buffer: str = ""
    tool_call_buffer: str = ""
    visible_xml_buffer: str = ""
    hidden_xml_closer: Optional[str] = None
    native_tool_call_parts: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    tool_calls_captured: List[ToolCall] = field(default_factory=list)
    executed_tool_signatures: Set[str] = field(default_factory=set)
    events: List[Dict[str, Any]] = field(default_factory=list)
    policy: Dict[str, Any] = field(default_factory=dict)
