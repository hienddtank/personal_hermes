from __future__ import annotations

import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .codex import ensure_allowed_path
from .config import (
    PROJECT_ROOT,
    WINBRIDGE_ALLOWED_SCRIPT_ROOTS,
    WINBRIDGE_ALLOWED_SHELLS,
    WINBRIDGE_DEFAULT_TIMEOUT,
    host_mount_path,
)
from .utils import now_iso, path_info, safe_decode

BRIDGE_JOBS: dict[str, dict[str, Any]] = {}
BRIDGE_JOBS_LOCK = threading.Lock()


def _normalize_script_path(raw: str) -> Path:
    path = host_mount_path(raw)
    if not path.exists():
        raise ValueError(f"Script does not exist: {path}")
    if path.suffix.lower() != ".ps1":
        raise ValueError("Only .ps1 scripts are allowed for winbridge.")
    for root in WINBRIDGE_ALLOWED_SCRIPT_ROOTS:
        try:
            path.relative_to(root)
            return path
        except ValueError:
            continue
    raise ValueError(
        f"Script not allowed: {path}. "
        f"Allowed script roots: {[str(x) for x in WINBRIDGE_ALLOWED_SCRIPT_ROOTS]}"
    )


def _normalize_args(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("Field 'args' must be a list of strings.")
    args: list[str] = []
    for item in raw:
        if isinstance(item, (str, int, float, bool)):
            args.append(str(item))
            continue
        raise ValueError("Field 'args' must only contain scalar values.")
    return args


def parse_winbridge_payload(data: dict[str, Any]) -> dict[str, Any]:
    shell = str(data.get("shell", "powershell")).strip().lower() or "powershell"
    if shell not in WINBRIDGE_ALLOWED_SHELLS:
        raise ValueError(
            f"Unsupported shell: {shell}. Allowed shells: {sorted(WINBRIDGE_ALLOWED_SHELLS)}"
        )

    script_raw = str(data.get("script", "")).strip()
    if not script_raw:
        raise ValueError("Field 'script' is required and cannot be empty.")
    script_path = _normalize_script_path(script_raw)

    timeout = int(data.get("timeout", WINBRIDGE_DEFAULT_TIMEOUT))
    if timeout <= 0:
        raise ValueError("Field 'timeout' must be a positive integer.")

    cwd_raw = data.get("cwd")
    cwd = ensure_allowed_path(cwd_raw) if cwd_raw else script_path.parent
    args = _normalize_args(data.get("args"))

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *args,
    ]

    return {
        "shell": shell,
        "script": script_path,
        "args": args,
        "cwd": cwd,
        "timeout": timeout,
        "cmd": cmd,
    }


def winbridge_config_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "shell": config["shell"],
        "script": str(config["script"]),
        "script_info": path_info(str(config["script"])),
        "cwd": str(config["cwd"]),
        "cwd_info": path_info(str(config["cwd"])),
        "args": list(config["args"]),
        "timeout": config["timeout"],
        "cmd": list(config["cmd"]),
    }


def build_winbridge_result_payload(
    config: dict[str, Any],
    request_started: float,
    returncode: int,
    stdout_text: str,
    stderr_text: str,
    request_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok = returncode == 0
    return {
        "ok": ok,
        "stage": "completed" if ok else "bridge_exit_nonzero",
        "error": None if ok else "WinBridge command exited non-zero.",
        "time": now_iso(),
        "duration_seconds": round(time.time() - request_started, 3),
        **winbridge_config_summary(config),
        "returncode": returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_preview": stdout_text[:4000],
        "stderr_preview": stderr_text[:4000],
        "request_log": request_log,
        "allowed_script_roots": [str(x) for x in WINBRIDGE_ALLOWED_SCRIPT_ROOTS],
        "project_root": str(PROJECT_ROOT),
    }


def start_winbridge_job(
    config: dict[str, Any],
    request_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    job_id = f"bridge_{uuid.uuid4().hex[:12]}"
    created_at = now_iso()
    job = {
        "job_id": job_id,
        "ok": None,
        "done": False,
        "stage": "queued",
        "created_at": created_at,
        "updated_at": created_at,
        "started_at": None,
        "finished_at": None,
        "duration_seconds": None,
        "returncode": None,
        "error": None,
        "stdout": "",
        "stderr": "",
        "request_log": request_log,
        **winbridge_config_summary(config),
    }
    with BRIDGE_JOBS_LOCK:
        BRIDGE_JOBS[job_id] = job
    thread = threading.Thread(target=run_winbridge_job, args=(job_id,), daemon=True)
    thread.start()
    return get_winbridge_job_payload(job_id) or {"ok": False, "error": "job_not_found"}


def run_winbridge_job(job_id: str) -> None:
    with BRIDGE_JOBS_LOCK:
        job = BRIDGE_JOBS.get(job_id)
        if not job:
            return
        job["stage"] = "running"
        job["started_at"] = now_iso()
        job["updated_at"] = job["started_at"]
        job["started_monotonic"] = time.time()
        cmd = list(job["cmd"])
        cwd = str(job["cwd"])
        timeout = int(job["timeout"])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=timeout,
            shell=False,
            cwd=cwd,
        )
        stdout_text = safe_decode(proc.stdout)
        stderr_text = safe_decode(proc.stderr)
        _finish_winbridge_job(
            job_id,
            ok=proc.returncode == 0,
            stage="completed" if proc.returncode == 0 else "bridge_exit_nonzero",
            returncode=proc.returncode,
            error=None if proc.returncode == 0 else "WinBridge command exited non-zero.",
            stdout=stdout_text,
            stderr=stderr_text,
        )
    except subprocess.TimeoutExpired as e:
        _finish_winbridge_job(
            job_id,
            ok=False,
            stage="bridge_timeout",
            error=f"WinBridge command timed out after {timeout} seconds.",
            stdout=safe_decode(e.stdout or b""),
            stderr=safe_decode(e.stderr or b""),
        )
    except FileNotFoundError as e:
        _finish_winbridge_job(
            job_id,
            ok=False,
            stage="bridge_launch",
            error=str(e),
        )
    except Exception as e:
        _finish_winbridge_job(
            job_id,
            ok=False,
            stage="bridge_launch",
            error=str(e),
        )


def _finish_winbridge_job(
    job_id: str,
    *,
    ok: bool,
    stage: str,
    returncode: int | None = None,
    error: str | None = None,
    stdout: str = "",
    stderr: str = "",
) -> None:
    finished_at = now_iso()
    with BRIDGE_JOBS_LOCK:
        job = BRIDGE_JOBS.get(job_id)
        if not job:
            return
        started = float(job.get("started_monotonic") or time.time())
        job.update(
            {
                "ok": ok,
                "done": True,
                "stage": stage,
                "returncode": returncode,
                "error": error,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_preview": stdout[:4000],
                "stderr_preview": stderr[:4000],
                "finished_at": finished_at,
                "updated_at": finished_at,
                "duration_seconds": round(time.time() - started, 3),
            }
        )


def get_winbridge_job_payload(job_id: str) -> dict[str, Any] | None:
    with BRIDGE_JOBS_LOCK:
        job = BRIDGE_JOBS.get(job_id)
        if not job:
            return None
        snapshot = dict(job)
    return {
        "ok": bool(snapshot.get("ok")) if snapshot.get("done") else True,
        "job_id": job_id,
        "job_type": "winbridge",
        "done": bool(snapshot.get("done")),
        "running": not bool(snapshot.get("done")),
        "status_url": f"/winbridge/jobs/{job_id}",
        "created_at": snapshot.get("created_at"),
        "updated_at": snapshot.get("updated_at"),
        "started_at": snapshot.get("started_at"),
        "finished_at": snapshot.get("finished_at"),
        "duration_seconds": snapshot.get("duration_seconds"),
        "stage": snapshot.get("stage"),
        "returncode": snapshot.get("returncode"),
        "error": snapshot.get("error"),
        "stdout": snapshot.get("stdout", ""),
        "stderr": snapshot.get("stderr", ""),
        "stdout_preview": snapshot.get("stdout_preview", ""),
        "stderr_preview": snapshot.get("stderr_preview", ""),
        "request_log": snapshot.get("request_log"),
        "shell": snapshot.get("shell"),
        "script": snapshot.get("script"),
        "script_info": snapshot.get("script_info"),
        "cwd": snapshot.get("cwd"),
        "cwd_info": snapshot.get("cwd_info"),
        "args": snapshot.get("args"),
        "timeout": snapshot.get("timeout"),
        "cmd": snapshot.get("cmd"),
    }


def list_winbridge_jobs_payload() -> dict[str, Any]:
    with BRIDGE_JOBS_LOCK:
        job_ids = sorted(
            BRIDGE_JOBS,
            key=lambda item: str(BRIDGE_JOBS[item].get("created_at", "")),
            reverse=True,
        )
    jobs = []
    for job_id in job_ids:
        payload = get_winbridge_job_payload(job_id)
        if payload is not None:
            jobs.append(payload)
    return {
        "ok": True,
        "time": now_iso(),
        "count": len(jobs),
        "jobs": jobs,
    }
