from proxy.core_parts import SessionState, StreamStateMachine


def _run_chunks(chunks):
    session = SessionState(request_id="test-thinking")
    session.policy = {"visible_reasoning": False, "hide_raw_tool_xml": True, "tools": []}
    machine = StreamStateMachine(session, session.policy)
    visible = []
    for chunk in chunks:
        output = machine.advance_state(chunk)
        if output.text_delta:
            visible.append(output.text_delta)
    flushed = machine.flush()
    if flushed.text_delta:
        visible.append(flushed.text_delta)
    return "".join(visible), session


def test_strips_complete_thinking_block():
    visible, _ = _run_chunks(["hello <think>hidden</think> world"])
    assert visible == "hello  world"


def test_strips_open_tag_split_across_chunks():
    visible, _ = _run_chunks(["alpha <thi", "nk>hidden</think> omega"])
    assert visible == "alpha  omega"


def test_strips_close_tag_split_across_chunks():
    visible, _ = _run_chunks(["alpha <think>hidden</th", "ink> omega"])
    assert visible == "alpha  omega"


def test_keeps_visible_text_before_and_after_thinking():
    visible, _ = _run_chunks(["before ", "<think>hidden</think>", " after"])
    assert visible == "before  after"


def test_unfinished_thinking_block_fails_closed_to_empty_tail():
    visible, session = _run_chunks(["start <think>hidden forever"])
    assert visible == "start "
    assert session.reasoning_buffer == "hidden forever"

