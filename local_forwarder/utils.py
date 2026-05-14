from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .config import host_mount_path


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_decode(value: bytes | None) -> str:
    if not value:
        return ""
    return value.decode("utf-8", errors="replace")


def safe_log_slug(value: str, max_length: int = 80) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in value)
    slug = "_".join(part for part in cleaned.split("_") if part)
    return (slug[:max_length] or "root")


def bool_from_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def path_info(path_str: str | None) -> dict[str, Any] | None:
    if not path_str:
        return None
    try:
        p = host_mount_path(path_str)
        return {
            "input": path_str,
            "resolved": str(p),
            "exists": p.exists(),
            "is_dir": p.is_dir() if p.exists() else False,
            "is_file": p.is_file() if p.exists() else False,
        }
    except Exception as e:
        return {
            "input": path_str,
            "error": str(e),
        }


def route_path(raw_path: str) -> str:
    path = urlsplit(raw_path).path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return path
