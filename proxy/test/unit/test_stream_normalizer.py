from proxy.core_parts import SessionState, StreamStateMachine


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "echo",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }
]


def _run(chunks):
    session = SessionState(request_id="stream-normalizer")
    session.policy = {"visible_reasoning": False, "hide_raw_tool_xml": True, "tools": TOOLS}
    machine = StreamStateMachine(session, session.policy)
    visible = []
    calls = []
    malformed = False
    for chunk in chunks:
        output = machine.advance_state(chunk)
        if output.text_delta:
            visible.append(output.text_delta)
        if output.tool_call:
            calls.append(output.tool_call)
        malformed = malformed or output.is_malformed
    flushed = machine.flush()
    if flushed.text_delta:
        visible.append(flushed.text_delta)
    if flushed.tool_call:
        calls.append(flushed.tool_call)
    malformed = malformed or flushed.is_malformed
    return "".join(visible), calls, malformed


def test_tool_call_while_thinking_block_is_active_is_captured_without_visible_reasoning():
    visible, calls, malformed = _run(
        ["hello\n<think>hidden", '\n</think>\n<tool_call>{"name":"echo","arguments":{"text":"x"}}</tool_call>']
    )
    assert visible == "hello\n\n"
    assert not malformed
    assert len(calls) == 1
    assert calls[0].name == "echo"


def test_thinking_after_tool_call_does_not_leak():
    visible, calls, malformed = _run(
        ['<tool_call>{"name":"echo","arguments":{"text":"x"}}</tool_call><think>tail</think>done']
    )
    assert len(calls) == 1
    assert visible == ""
    assert not malformed


def test_multiple_tool_calls_require_separate_turns_and_no_partial_json_leaks():
    visible, calls, malformed = _run(
        ['<tool_call>{"name":"echo","arguments":{"text":"1"}}</tool_call> trailing']
    )
    assert len(calls) == 1
    assert visible == ""
    assert not malformed


def test_duplicate_tool_call_ids_are_not_created_by_parser_layer():
    visible, calls, malformed = _run(
        ['<tool_call>{"name":"echo","arguments":{"text":"1"}}</tool_call>']
    )
    assert visible == ""
    assert len({call.id for call in calls}) == 1
    assert not malformed


def test_tool_result_without_matching_tool_call_is_outside_stream_machine_scope():
    visible, calls, malformed = _run(["<tool_response>orphan</tool_response> visible"])
    assert "visible" in visible
    assert calls == []
    assert not malformed

