from proxy.observability.failure_classifier import classify_failure_sample
from proxy.observability.sample_schema import new_sample


def _sample(**overrides):
    return new_sample(**overrides).to_dict()


def test_classifies_thinking_leak():
    result = classify_failure_sample(_sample(observed={"visible_text": "<think>x</think>", "has_done": True}))
    assert result.category == "THINKING_LEAK"


def test_classifies_empty_upstream_body():
    result = classify_failure_sample(_sample(observed={"empty_response": True, "has_done": True}, raw={"llama_chunks": []}))
    assert result.category == "EMPTY_UPSTREAM_BODY"


def test_classifies_empty_after_thinking_strip():
    result = classify_failure_sample(
        _sample(raw={"llama_chunks": ["<think>hidden</think>"]}, observed={"visible_text": "", "tool_call_count": 0, "has_done": True})
    )
    assert result.category == "EMPTY_AFTER_THINKING_STRIP"


def test_classifies_missing_done():
    result = classify_failure_sample(_sample(mode="streaming", observed={"has_done": False}))
    assert result.category == "MISSING_DONE"


def test_classifies_invalid_sse_json():
    result = classify_failure_sample(_sample(observed={"invalid_json": True, "has_done": True}))
    assert result.category == "INVALID_SSE_JSON"


def test_classifies_tool_call_incomplete():
    result = classify_failure_sample(_sample(observed={"incomplete_tool_call": True, "has_done": True}))
    assert result.category == "TOOL_CALL_INCOMPLETE"


def test_classifies_backend_timeout():
    result = classify_failure_sample(_sample(failure={"type": "EXCEPTION", "message": "request timeout"}))
    assert result.category == "BACKEND_TIMEOUT"


def test_classifies_connection_refused():
    result = classify_failure_sample(_sample(failure={"type": "EXCEPTION", "message": "connection refused by host"}))
    assert result.category == "BACKEND_CONNECTION_REFUSED"


def test_unknown_stays_unknown():
    result = classify_failure_sample(_sample(observed={"has_done": True}))
    assert result.category == "UNKNOWN"

