from proxy.core_parts import SessionState, StreamStateMachine, ToolCallParser


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }
]


def _machine():
    session = SessionState(request_id="test-tool-buffer")
    session.policy = {"visible_reasoning": False, "hide_raw_tool_xml": True, "tools": TOOLS}
    return StreamStateMachine(session, session.policy), session


def test_tool_call_in_one_chunk_is_emitted_only_when_complete():
    machine, _ = _machine()
    output = machine.advance_state('<tool_call>{"name":"search","arguments":{"query":"abc"}}</tool_call>')
    assert output.tool_call is not None
    assert output.tool_call.name == "search"
    assert output.tool_call.arguments == {"query": "abc"}


def test_tool_call_split_across_chunks_waits_for_completion():
    machine, _ = _machine()
    partial = machine.advance_state('<tool_call>{"name":"search",')
    assert partial.tool_call is None
    complete = machine.advance_state('"arguments":{"query":"abc"}}</tool_call>')
    assert complete.tool_call is not None
    assert complete.tool_call.arguments == {"query": "abc"}


def test_nested_json_arguments_are_preserved():
    tool_call = ToolCallParser.parse_tool_call_xml(
        '<tool_call>{"name":"search","arguments":{"query":"abc","meta":{"page":1}}}</tool_call>'
    )
    assert tool_call is not None
    assert tool_call.arguments["meta"] == {"page": 1}


def test_escaped_quotes_in_arguments_are_preserved():
    tool_call = ToolCallParser.parse_tool_call_xml(
        '<tool_call>{"name":"search","arguments":{"query":"say \\"hi\\" now"}}</tool_call>'
    )
    assert tool_call is not None
    assert tool_call.arguments["query"] == 'say "hi" now'


def test_literal_think_text_inside_json_string_is_not_stripped():
    tool_call = ToolCallParser.parse_tool_call_xml(
        '<tool_call>{"name":"search","arguments":{"query":"literal <think> token"}}</tool_call>'
    )
    assert tool_call is not None
    assert tool_call.arguments["query"] == "literal <think> token"

