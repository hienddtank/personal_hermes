from dataclasses import asdict, dataclass
from typing import Any, Dict

from .sample_schema import sample_to_dict


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    layer: str
    replayable: bool
    recommended_action: str
    patch_allowed_later: bool
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_failure_sample(sample: Dict[str, Any]) -> ClassificationResult:
    data = sample_to_dict(sample)
    observed = data.get("observed") or {}
    raw = data.get("raw") or {}
    failure = data.get("failure") or {}
    mode = data.get("mode")
    visible_text = str(observed.get("visible_text") or "")
    raw_text = "\n".join(str(chunk) for chunk in raw.get("llama_chunks") or [])
    exception_text = " ".join(
        str(part or "")
        for part in (
            failure.get("message"),
            failure.get("exception_type"),
            raw.get("exception_text"),
            failure.get("stacktrace"),
        )
    ).lower()

    if "<think>" in visible_text or "</think>" in visible_text or observed.get("thinking_leaked"):
        return ClassificationResult("THINKING_LEAK", "normalizer", True, "strip_thinking", True, 0.99)
    if observed.get("invalid_json"):
        return ClassificationResult("INVALID_SSE_JSON", "sse", True, "reject_invalid_sse", True, 0.95)
    if "timeout" in exception_text:
        return ClassificationResult("BACKEND_TIMEOUT", "upstream", True, "retry_or_timeout", False, 0.9)
    if "connection refused" in exception_text:
        return ClassificationResult("BACKEND_CONNECTION_REFUSED", "upstream", True, "check_backend_connectivity", False, 0.9)
    if observed.get("incomplete_tool_call"):
        return ClassificationResult("TOOL_CALL_INCOMPLETE", "tool_buffer", True, "fail_closed_or_fix_tool_buffer", True, 0.95)
    if failure.get("type") == "NORMALIZER_ERROR":
        return ClassificationResult("PROXY_EXCEPTION", "normalizer", True, "fix_normalizer", True, 0.9)
    if observed.get("empty_response") and not raw_text.strip():
        return ClassificationResult("EMPTY_UPSTREAM_BODY", "upstream", True, "handle_empty_upstream", True, 0.95)
    if raw_text.strip() and "<think>" in raw_text and not visible_text.strip() and not observed.get("tool_call_count"):
        return ClassificationResult("EMPTY_AFTER_THINKING_STRIP", "normalizer", True, "preserve_visible_text", True, 0.92)
    if observed.get("tool_call_count", 0) > 1 and failure.get("type") == "DUPLICATE_TOOL_CALL":
        return ClassificationResult("TOOL_CALL_DUPLICATED", "tool_buffer", True, "dedupe_tool_calls", True, 0.9)
    if failure.get("type") == "TOOL_RESULT_ORPHANED":
        return ClassificationResult("TOOL_RESULT_ORPHANED", "tool_execution", True, "match_tool_results", True, 0.9)
    if failure.get("type") == "INVALID_OPENAI_CONTRACT":
        return ClassificationResult("INVALID_OPENAI_CONTRACT", "adapter", True, "fix_contract", True, 0.95)
    if "status" in exception_text and "5" in exception_text:
        return ClassificationResult("BACKEND_ERROR_STATUS", "upstream", True, "handle_backend_error", False, 0.75)
    if failure.get("type") == "STREAM_CLOSED_EARLY":
        return ClassificationResult("STREAM_CLOSED_EARLY", "stream", True, "fail_closed", True, 0.9)
    if failure.get("type") == "TOOL_ARGUMENTS_INVALID_JSON":
        return ClassificationResult("TOOL_ARGUMENTS_INVALID_JSON", "tool_buffer", True, "reject_invalid_tool_json", True, 0.95)
    if failure.get("type") == "THINKING_TAG_SPLIT":
        return ClassificationResult("THINKING_TAG_SPLIT", "normalizer", True, "stabilize_chunk_split_logic", True, 0.85)
    if mode == "streaming" and not observed.get("has_done"):
        return ClassificationResult("MISSING_DONE", "stream", True, "require_done", True, 0.95)
    return ClassificationResult("UNKNOWN", "unknown", True, "needs_review", False, 0.2)
