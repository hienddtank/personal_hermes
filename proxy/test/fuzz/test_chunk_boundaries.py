import pytest

from proxy.core_parts import SessionState, StreamStateMachine


def run_chunks(chunks):
    session = SessionState(request_id="fuzz")
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
    return "".join(visible)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("before<think>hidden</think>after", "beforeafter"),
        ('<tool_call>{"name":"x","arguments":{"a":"b"}}</tool_call>', ""),
        ("alpha<think>hidden</think>omega", "alphaomega"),
    ],
)
def test_chunk_boundary_invariance(text, expected):
    baseline = run_chunks([text])
    assert baseline == expected
    for index in range(1, len(text)):
        split_result = run_chunks([text[:index], text[index:]])
        assert split_result == baseline, f"boundary {index} changed output"

