import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

CURRENT_SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _deep_merge(defaults: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(defaults)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def sample_defaults() -> Dict[str, Any]:
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "id": "error_000000",
        "timestamp": _utc_now_iso(),
        "request_id": "",
        "source": "live_proxy",
        "mode": "streaming",
        "model": "unknown",
        "category": "UNKNOWN",
        "severity": "unknown",
        "status": "quarantine",
        "failure": {
            "type": "UNKNOWN",
            "message": "",
            "exception_type": None,
            "stacktrace": None,
        },
        "request_summary": {
            "endpoint": "/v1/chat/completions",
            "stream": True,
            "has_tools": False,
            "message_count": 0,
            "body_sha256": "",
        },
        "raw": {
            "llama_chunks": [],
            "client_chunks": [],
            "exception_text": "",
            "state_trace": [],
        },
        "observed": {
            "visible_text": "",
            "tool_call_count": 0,
            "has_done": False,
            "empty_response": False,
            "thinking_leaked": False,
            "invalid_json": False,
            "incomplete_tool_call": False,
        },
        "expected_behavior": {
            "mode": "needs_review",
            "notes": "",
        },
        "redaction": {
            "redacted": True,
            "rules_applied": [],
        },
        "fingerprint": "",
    }


@dataclass
class FailureSample:
    data: Dict[str, Any] = field(default_factory=sample_defaults)

    def to_dict(self) -> Dict[str, Any]:
        return deepcopy(self.data)

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True)


def new_sample(**overrides: Any) -> FailureSample:
    return FailureSample(_deep_merge(sample_defaults(), overrides))


def sample_to_dict(sample: FailureSample | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(sample, FailureSample):
        return sample.to_dict()
    return _deep_merge(sample_defaults(), sample)


def dump_sample_json(sample: FailureSample | Dict[str, Any]) -> str:
    return json.dumps(sample_to_dict(sample), ensure_ascii=False, indent=2, sort_keys=True)


def load_sample(source: str | bytes | Dict[str, Any]) -> FailureSample:
    if isinstance(source, dict):
        return FailureSample(sample_to_dict(source))
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    data = json.loads(source)
    return FailureSample(sample_to_dict(data))

