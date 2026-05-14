from __future__ import annotations

import json
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from typing import Any

from .config import (
    LOG_DIR,
    LOG_HEADER_ALLOWLIST,
    LOG_PRUNE_INTERVAL_SECONDS,
    LOG_RETENTION_DAYS,
)
from .utils import now_iso, route_path, safe_decode, safe_log_slug

LAST_LOG_PRUNE = 0.0


def request_log_config() -> dict[str, Any]:
    return {
        "directory": str(LOG_DIR),
        "retention_days": LOG_RETENTION_DAYS,
        "prune_interval_seconds": LOG_PRUNE_INTERVAL_SECONDS,
        "file_format": "one JSON file per inbound HTTP request",
    }


def prune_old_request_logs(force: bool = False) -> dict[str, Any]:
    global LAST_LOG_PRUNE

    now = time.time()
    if not force and now - LAST_LOG_PRUNE < LOG_PRUNE_INTERVAL_SECONDS:
        return {"ok": True, "skipped": True, "deleted_count": 0}

    deleted_count = 0
    errors: list[str] = []

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_root = LOG_DIR.resolve()
        cutoff = now - (LOG_RETENTION_DAYS * 24 * 60 * 60)

        for candidate in LOG_DIR.glob("*.json"):
            try:
                resolved = candidate.resolve()
                resolved.relative_to(log_root)
                if resolved.is_file() and resolved.stat().st_mtime < cutoff:
                    resolved.unlink()
                    deleted_count += 1
            except Exception as e:
                errors.append(f"{candidate.name}: {e}")
    except Exception as e:
        errors.append(str(e))

    LAST_LOG_PRUNE = now
    return {
        "ok": not errors,
        "skipped": False,
        "deleted_count": deleted_count,
        "errors": errors,
    }


def save_request_log(
    handler: BaseHTTPRequestHandler,
    raw_body: bytes | None = None,
    stage: str = "received",
    error: str | None = None,
) -> dict[str, Any]:
    raw_body = raw_body or b""
    method = getattr(handler, "command", "UNKNOWN")
    raw_path = getattr(handler, "path", "/")
    route = route_path(raw_path)
    client_host = None
    client_port = None
    if getattr(handler, "client_address", None):
        client_host = handler.client_address[0]
        client_port = handler.client_address[1]

    headers: dict[str, str] = {}
    request_headers = getattr(handler, "headers", None)
    if request_headers:
        headers = {
            name: value
            for name, value in request_headers.items()
            if name.lower() in LOG_HEADER_ALLOWLIST
        }

    record: dict[str, Any] = {
        "time": now_iso(),
        "stage": stage,
        "method": method,
        "path": raw_path,
        "route_path": route,
        "client": {
            "host": client_host,
            "port": client_port,
        },
        "headers": headers,
        "body_bytes": len(raw_body),
        "body_encoding": "utf-8 with replacement for invalid bytes",
        "body": safe_decode(raw_body),
        "retention_days": LOG_RETENTION_DAYS,
    }
    if error:
        record["error"] = error

    try:
        prune_result = prune_old_request_logs()
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = (
            f"{stamp}_{safe_log_slug(str(method), 20)}_"
            f"{safe_log_slug(route)}.json"
        )
        log_path = LOG_DIR / filename
        log_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "path": str(log_path),
            "body_bytes": len(raw_body),
            "prune": prune_result,
        }
    except Exception as e:
        print(f"[{now_iso()}] request log write failed: {e}")
        return {
            "ok": False,
            "error": str(e),
            "body_bytes": len(raw_body),
            "directory": str(LOG_DIR),
        }
