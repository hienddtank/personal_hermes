import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .failure_classifier import classify_failure_sample
from .redactor import redact_any, summarize_request
from .sample_schema import new_sample
from .sample_writer import write_sample_atomic


def _truthy_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class CaptureContext:
    request_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    mode: str = "streaming"
    model: str = "unknown"
    llama_chunks: List[str] = field(default_factory=list)
    client_chunks: List[str] = field(default_factory=list)
    state_trace: List[Dict[str, Any]] = field(default_factory=list)
    observed: Dict[str, Any] = field(default_factory=dict)


def capture_failure_sample(
    context: CaptureContext,
    *,
    failure_type: str,
    message: str = "",
    exception: Optional[BaseException] = None,
    source: str = "live_proxy",
) -> Optional[Path]:
    if not _truthy_env("PROXY_CAPTURE_FAILURES", "0"):
        return None
    try:
        redacted_payload, rules = redact_any(context.payload)
        sample = new_sample(
            request_id=context.request_id,
            source=source,
            mode=context.mode,
            model=context.model,
            failure={
                "type": failure_type,
                "message": message or (str(exception) if exception else ""),
                "exception_type": type(exception).__name__ if exception else None,
                "stacktrace": traceback.format_exc() if exception and _truthy_env("PROXY_CAPTURE_STACKTRACE", "1") else None,
            },
            request_summary=summarize_request(redacted_payload),
            raw={
                "llama_chunks": context.llama_chunks if _truthy_env("PROXY_CAPTURE_RAW_CHUNKS", "0") else [],
                "client_chunks": context.client_chunks if _truthy_env("PROXY_CAPTURE_CLIENT_CHUNKS", "1") else [],
                "exception_text": str(exception) if exception else "",
                "state_trace": context.state_trace,
            },
            observed=context.observed,
            redaction={"redacted": True, "rules_applied": rules},
        ).to_dict()
        classification = classify_failure_sample(sample).to_dict()
        sample["category"] = classification["category"]
        capture_dir = Path(os.getenv("PROXY_CAPTURE_DIR", "proxy/test/samples/quarantine"))
        written_path, created = write_sample_atomic(sample, capture_dir)
        if written_path and created:
            print(
                "Captured proxy failure sample:\n"
                f"  id: {written_path.stem}\n"
                f"  category: {sample['category']}\n"
                f"  path: {written_path.as_posix()}\n"
                f"  replayable: {classification['replayable']}"
            )
        return written_path
    except Exception:
        return None
