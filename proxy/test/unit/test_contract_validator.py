from proxy.observability.contract_validator import validate_non_stream_response, validate_sse_events


def test_valid_openai_style_response_passes():
    result = validate_non_stream_response(
        {
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        }
    )
    assert result.ok


def test_response_containing_think_fails():
    result = validate_non_stream_response(
        {
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "<think>x</think>"}, "finish_reason": "stop"}],
        }
    )
    assert not result.ok


def test_missing_choices_fails():
    result = validate_non_stream_response({"object": "chat.completion"})
    assert not result.ok


def test_malformed_sse_fails():
    result = validate_sse_events(["data: {not-json}", "data: [DONE]"])
    assert not result.ok


def test_missing_done_fails_for_streaming_mode():
    result = validate_sse_events(
        ['data: {"choices":[{"delta":{"content":"hi"}}]}']
    )
    assert not result.ok

