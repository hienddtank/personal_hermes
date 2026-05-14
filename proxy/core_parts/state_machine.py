from datetime import datetime
from typing import Any, Dict, List

from .config import MAX_TOOL_CALL_BUFFER, OPEN_TAGS, THINK_TAGS, logger
from .models import ParsedOutput, SessionState, StreamState
from .parsing import ToolCallParser
from .text_utils import (
    escape_xml_like_text,
    salvage_visible_text_after_orphan_tool_tag,
    scrub_visible_tool_xml,
    split_safe_prefix,
    tool_call_block_is_structural,
    tool_call_block_looks_like_json,
    tool_capture_buffer_is_actionable,
)


class StreamStateMachine:
    def __init__(self, session: SessionState, policy: Dict[str, Any]):
        self.session = session
        self.policy = policy
        self.parser = ToolCallParser()

    def advance_state(self, delta: str) -> ParsedOutput:
        self.session.raw_text_buffer += delta
        self.session.pending_text += delta
        emitted: List[str] = []
        while self.session.pending_text:
            if self.session.current_state == StreamState.PASS_THROUGH:
                output = self._handle_pass_through(emitted)
            elif self.session.current_state == StreamState.THINKING:
                output = self._handle_thinking(emitted)
            elif self.session.current_state == StreamState.TOOL_CAPTURE:
                output = self._handle_tool_capture(emitted)
            else:
                output = ParsedOutput(state=self.session.current_state)
            if output.tool_call or output.is_malformed:
                output.text_delta = self._visible_text("".join(emitted))
                self.session.normalized_text_buffer += output.text_delta
                return output
            if not output.text_delta:
                break
        text_delta = self._visible_text("".join(emitted))
        self.session.normalized_text_buffer += text_delta
        return ParsedOutput(state=self.session.current_state, text_delta=text_delta)

    def flush(self) -> ParsedOutput:
        text_delta = ""
        if self.session.current_state in {StreamState.PASS_THROUGH, StreamState.THINKING}:
            text_delta = self.session.pending_text
            if self.session.current_state == StreamState.THINKING and not self.policy.get(
                "visible_reasoning", True
            ):
                text_delta = salvage_visible_text_after_orphan_tool_tag(
                    self.session.reasoning_buffer + text_delta
                )
            else:
                text_delta = self._visible_text(text_delta)
            self.session.pending_text = ""
        elif self.session.current_state == StreamState.TOOL_CAPTURE:
            if not tool_capture_buffer_is_actionable(self.session):
                text_delta = self._visible_text(escape_xml_like_text(self.session.tool_call_buffer))
                self.session.tool_call_buffer = ""
                self.session.pending_text = ""
                self._transition(StreamState.PASS_THROUGH)
                self.session.normalized_text_buffer += text_delta
                return ParsedOutput(state=self.session.current_state, text_delta=text_delta)
            self._transition(StreamState.ERROR)
            return ParsedOutput(state=StreamState.ERROR, is_malformed=True)
        self.session.normalized_text_buffer += text_delta
        return ParsedOutput(state=self.session.current_state, text_delta=text_delta)

    def _visible_text(self, text: str) -> str:
        if self.policy.get("hide_raw_tool_xml", True):
            return scrub_visible_tool_xml(text, self.session)
        return text

    def _handle_pass_through(self, emitted: List[str]) -> ParsedOutput:
        pending = self.session.pending_text
        think_pos = pending.find("<think>")
        tool_pos = pending.find("<tool_call>")
        positions = [pos for pos in (think_pos, tool_pos) if pos != -1]
        if positions:
            first = min(positions)
            if first:
                emitted.append(pending[:first])
            if first == think_pos:
                self.session.pending_text = pending[first + len("<think>") :]
                self._transition(StreamState.THINKING)
            else:
                self.session.pending_text = pending[first:]
                self._transition(StreamState.TOOL_CAPTURE)
            return ParsedOutput(state=self.session.current_state, text_delta="progress")
        safe, hold = split_safe_prefix(pending, OPEN_TAGS)
        if safe:
            emitted.append(safe)
            self.session.pending_text = hold
            return ParsedOutput(state=StreamState.PASS_THROUGH, text_delta="progress")
        return ParsedOutput(state=StreamState.PASS_THROUGH)

    def _handle_thinking(self, emitted: List[str]) -> ParsedOutput:
        pending = self.session.pending_text
        close_pos = pending.find("</think>")
        tool_pos = pending.find("<tool_call>")
        positions = [pos for pos in (close_pos, tool_pos) if pos != -1]
        if positions:
            first = min(positions)
            reasoning = pending[:first]
            self.session.reasoning_buffer += reasoning
            if self.policy.get("visible_reasoning", True):
                emitted.append(reasoning)
            if first == tool_pos:
                self.session.pending_text = pending[first:]
                self._transition(StreamState.TOOL_CAPTURE)
            else:
                self.session.pending_text = pending[first + len("</think>") :]
                self._transition(StreamState.PASS_THROUGH)
            return ParsedOutput(state=self.session.current_state, text_delta="progress")
        safe, hold = split_safe_prefix(pending, THINK_TAGS)
        if safe:
            self.session.reasoning_buffer += safe
            if self.policy.get("visible_reasoning", True):
                emitted.append(safe)
            self.session.pending_text = hold
            return ParsedOutput(state=StreamState.THINKING, text_delta="progress")
        return ParsedOutput(state=StreamState.THINKING)

    def _handle_tool_capture(self, emitted: List[str]) -> ParsedOutput:
        self.session.tool_call_buffer += self.session.pending_text
        self.session.pending_text = ""
        if len(self.session.tool_call_buffer) > MAX_TOOL_CALL_BUFFER:
            self._transition(StreamState.ERROR)
            return ParsedOutput(state=StreamState.ERROR, is_malformed=True)
        complete_tool = self.parser.capture_complete_tool_call(self.session.tool_call_buffer)
        if not complete_tool:
            return ParsedOutput(state=StreamState.TOOL_CAPTURE)
        tool_call = self.parser.parse_tool_call_xml(complete_tool)
        if not tool_call:
            if "<function=" not in complete_tool and not tool_call_block_looks_like_json(complete_tool):
                return self._demote_tool_capture_to_text(complete_tool, emitted)
            self._transition(StreamState.ERROR)
            return ParsedOutput(state=StreamState.ERROR, is_malformed=True)
        if not tool_call_block_is_structural(self.session, complete_tool):
            return self._demote_tool_capture_to_text(complete_tool, emitted)
        tool_call = self.parser.sanitize_tool_arguments(tool_call)
        tool_schema = self.parser.tool_schema_from_openai_tools(self.policy.get("tools", []))
        if not self.parser.validate_tool_call(tool_call, tool_schema):
            self._transition(StreamState.ERROR)
            return ParsedOutput(state=StreamState.ERROR, is_malformed=True)
        end = self.session.tool_call_buffer.find("</tool_call>") + len("</tool_call>")
        self.session.pending_text = self.session.tool_call_buffer[end:]
        self.session.tool_call_buffer = ""
        self.session.tool_calls_captured.append(tool_call)
        self._transition(StreamState.WAIT_TOOL_RESULT)
        return ParsedOutput(state=StreamState.WAIT_TOOL_RESULT, tool_call=tool_call)

    def _demote_tool_capture_to_text(self, complete_tool: str, emitted: List[str]) -> ParsedOutput:
        end = self.session.tool_call_buffer.find("</tool_call>") + len("</tool_call>")
        self.session.pending_text = self.session.tool_call_buffer[end:]
        self.session.tool_call_buffer = ""
        emitted.append(escape_xml_like_text(complete_tool))
        self._transition(StreamState.PASS_THROUGH)
        return ParsedOutput(state=StreamState.PASS_THROUGH, text_delta="progress")

    def _transition(self, new_state: StreamState) -> None:
        old_state = self.session.current_state
        if old_state == new_state:
            return
        self.session.current_state = new_state
        self.session.events.append(
            {
                "type": "state_transition",
                "old_state": old_state.value,
                "new_state": new_state.value,
                "time": datetime.now().isoformat(),
            }
        )
        logger.debug("[%s] state %s -> %s", self.session.request_id, old_state, new_state)
