import hashlib
import json
import os
import re
from typing import Any, Dict, List, Tuple

REDACTED = "[REDACTED]"
SENSITIVE_KEY_RE = re.compile(
    r"(authorization|cookie|password|secret|api_?key|access_?token|refresh_?token)",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"(Bearer\s+)([A-Za-z0-9._~+/=-]+)", re.IGNORECASE)
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})\b"
)


def _truthy_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _truncate_text(text: str) -> str:
    max_chars = int(os.getenv("PROXY_CAPTURE_MAX_CHARS", "200000"))
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"


def redact_string(value: str, rules: List[str]) -> str:
    try:
        updated = value
        if BEARER_RE.search(updated):
            updated = BEARER_RE.sub(r"\1[REDACTED]", updated)
            rules.append("bearer_token")
        if _truthy_env("PROXY_CAPTURE_REDACT_PRIVATE_IPS", "0") and PRIVATE_IP_RE.search(updated):
            updated = PRIVATE_IP_RE.sub(REDACTED, updated)
            rules.append("private_ip")
        updated = _truncate_text(updated)
        return updated
    except Exception:
        return REDACTED


def redact_value(value: Any, rules: List[str], key_hint: str = "") -> Any:
    try:
        if isinstance(value, dict):
            return redact_dict(value, rules)
        if isinstance(value, list):
            return [redact_value(item, rules, key_hint=key_hint) for item in value]
        if isinstance(value, str):
            if key_hint and SENSITIVE_KEY_RE.search(key_hint):
                rules.append(f"key:{key_hint.lower()}")
                return REDACTED
            return redact_string(value, rules)
        return value
    except Exception:
        rules.append("redactor_exception")
        return REDACTED


def redact_dict(data: Dict[str, Any], rules: List[str] | None = None) -> Dict[str, Any]:
    applied = rules if rules is not None else []
    redacted: Dict[str, Any] = {}
    for key, value in (data or {}).items():
        if SENSITIVE_KEY_RE.search(str(key)):
            applied.append(f"key:{str(key).lower()}")
            redacted[key] = REDACTED
            continue
        redacted[key] = redact_value(value, applied, key_hint=str(key))
    return redacted


def redact_any(data: Any) -> Tuple[Any, List[str]]:
    rules: List[str] = []
    redacted = redact_value(data, rules)
    return redacted, sorted(set(rules))


def summarize_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    body_text = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
    message_count = len((payload or {}).get("messages") or [])
    has_tools = bool((payload or {}).get("tools"))
    return {
        "endpoint": "/v1/chat/completions",
        "stream": bool((payload or {}).get("stream")),
        "has_tools": has_tools,
        "message_count": message_count,
        "body_sha256": sha256_text(body_text),
    }
