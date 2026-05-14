import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple

from .sample_deduper import is_duplicate_sample
from .sample_schema import dump_sample_json, sample_to_dict


def compute_fingerprint(sample: Dict[str, Any]) -> str:
    failure = sample.get("failure") or {}
    observed = sample.get("observed") or {}
    raw = sample.get("raw") or {}
    normalized = {
        "category": sample.get("category", "UNKNOWN"),
        "failure_type": failure.get("type"),
        "failure_message": failure.get("message"),
        "state_trace": raw.get("state_trace"),
        "tool_call_count": observed.get("tool_call_count"),
        "visible_text": observed.get("visible_text"),
        "llama_chunks": raw.get("llama_chunks"),
    }
    return hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _filename_for(sample: Dict[str, Any]) -> str:
    unix_ms = int(time.time() * 1000)
    short_hash = sample["fingerprint"][:10]
    return f"error_{unix_ms}_{short_hash}.json"


def write_sample_atomic(sample: Dict[str, Any], directory: Path) -> Tuple[Path | None, bool]:
    data = sample_to_dict(sample)
    data["status"] = "quarantine"
    data["fingerprint"] = compute_fingerprint(data)
    directory.mkdir(parents=True, exist_ok=True)
    if is_duplicate_sample(directory, data["fingerprint"]):
        return None, False
    final_path = directory / _filename_for(data)
    temp_path = final_path.with_suffix(".tmp")
    temp_path.write_text(dump_sample_json(data), encoding="utf-8")
    temp_path.replace(final_path)
    return final_path, True

