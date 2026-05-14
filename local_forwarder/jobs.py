from __future__ import annotations

import subprocess
import threading
import time
import uuid
from typing import Any

from .codex import (
    build_codex_hints,
    empty_output_error,
    output_state,
    result_stage,
    run_config_summary,
)
from .config import (
    ASYNC_JOB_RETENTION_SECONDS,
    ASYNC_OUTPUT_LIMIT_CHARS,
    ASYNC_POLL_AFTER_SECONDS,
    REPO_ALIASES,
)
from .utils import now_iso, safe_decode

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def prune_old_jobs() -> None:
    cutoff = time.time() - ASYNC_JOB_RETENTION_SECONDS
    with JOBS_LOCK:
        expired = [
            job_id
            for job_id, job in JOBS.items()
            if job.get("finished_monotonic") and job["finished_monotonic"] < cutoff
        ]
        for job_id in expired:
            JOBS.pop(job_id, None)


def append_job_output(job_id: str, stream_name: str, chunk: bytes) -> None:
    text = safe_decode(chunk)
    if not text:
        return

    truncated_key = f"{stream_name}_truncated_chars"
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        combined = str(job.get(stream_name, "")) + text
        if len(combined) > ASYNC_OUTPUT_LIMIT_CHARS:
            overflow = len(combined) - ASYNC_OUTPUT_LIMIT_CHARS
            job[truncated_key] = int(job.get(truncated_key, 0)) + overflow
            combined = combined[overflow:]
        job[stream_name] = combined
        job["updated_at"] = now_iso()


def read_process_stream(job_id: str, pipe: Any, stream_name: str) -> None:
    if pipe is None:
        return
    try:
        while True:
            chunk = pipe.read(4096)
            if not chunk:
                break
            append_job_output(job_id, stream_name, chunk)
    except Exception as e:
        append_job_output(
            job_id,
            "stderr",
            f"\nforwarder failed to read {stream_name}: {e}\n".encode("utf-8"),
        )
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def start_codex_job(
    config: dict[str, Any],
    request_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prune_old_jobs()
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    created_at = now_iso()
    job = {
        "job_id": job_id,
        "ok": None,
        "stage": "queued",
        "created_at": created_at,
        "updated_at": created_at,
        "started_at": None,
        "finished_at": None,
        "finished_monotonic": None,
        "duration_seconds": None,
        "returncode": None,
        "error": None,
        "empty_output": False,
        "output_state": "empty",
        "process_ok": None,
        "stdout": "",
        "stderr": "",
        "stdout_truncated_chars": 0,
        "stderr_truncated_chars": 0,
        "hints": [],
        "request_log": request_log,
        **run_config_summary(config),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job

    thread = threading.Thread(target=run_codex_job, args=(job_id,), daemon=True)
    thread.start()
    return get_job_payload(job_id) or {"ok": False, "error": "job_not_found"}


def run_codex_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job["stage"] = "running"
        job["started_at"] = now_iso()
        job["started_monotonic"] = time.time()
        job["updated_at"] = job["started_at"]
        cmd = list(job["cmd"])
        cwd = str(job["cwd"])
        timeout = int(job["timeout"])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            shell=False,
            cwd=cwd,
        )
    except FileNotFoundError as e:
        finish_job(
            job_id,
            ok=False,
            stage="launch_codex",
            error=str(e),
            hints=[
                "This usually means cmd.exe, codex.cmd, or a dependency like node could not be started.",
            ],
        )
        return
    except Exception as e:
        finish_job(job_id, ok=False, stage="run_codex", error=str(e))
        return

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job:
            job["pid"] = proc.pid
            job["updated_at"] = now_iso()

    readers = [
        threading.Thread(
            target=read_process_stream,
            args=(job_id, proc.stdout, "stdout"),
            daemon=True,
        ),
        threading.Thread(
            target=read_process_stream,
            args=(job_id, proc.stderr, "stderr"),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()

    timed_out = False
    returncode: int | None = None
    while True:
        returncode = proc.poll()
        now = time.time()
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job:
                started = float(job.get("started_monotonic") or now)
                job["elapsed_seconds"] = round(now - started, 3)
                job["updated_at"] = now_iso()
        if returncode is not None:
            break
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            started = float(job.get("started_monotonic") or now) if job else now
        if now - started >= timeout:
            timed_out = True
            try:
                proc.kill()
            except Exception:
                pass
            returncode = proc.wait()
            break
        time.sleep(1)

    for reader in readers:
        reader.join(timeout=2)

    if returncode is None:
        returncode = proc.returncode if proc.returncode is not None else -1

    if timed_out:
        finish_job(
            job_id,
            ok=False,
            stage="run_timeout",
            returncode=returncode,
            error=f"Codex timed out after {timeout} seconds.",
            hints=["Increase the timeout for larger tasks, or split the prompt into smaller work."],
        )
        return

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        stdout_text = str(job.get("stdout", "")) if job else ""
        stderr_text = str(job.get("stderr", "")) if job else ""
    process_ok = returncode == 0
    stage = result_stage(returncode, stdout_text, stderr_text)
    finish_job(
        job_id,
        ok=process_ok and stage != "empty_output",
        stage=stage,
        returncode=returncode,
        error=empty_output_error(returncode, stdout_text, stderr_text),
        hints=build_codex_hints(process_ok, stderr_text, stdout_text),
    )


def finish_job(
    job_id: str,
    ok: bool,
    stage: str,
    returncode: int | None = None,
    error: str | None = None,
    hints: list[str] | None = None,
) -> None:
    now = time.time()
    finished_at = now_iso()
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        started = float(job.get("started_monotonic") or now)
        stdout_text = str(job.get("stdout", ""))
        stderr_text = str(job.get("stderr", ""))
        state = output_state(stdout_text, stderr_text)
        empty_output = stage == "empty_output"
        job.update(
            {
                "ok": ok,
                "stage": stage,
                "returncode": returncode,
                "error": error,
                "empty_output": empty_output,
                "output_state": state,
                "process_ok": returncode == 0 if returncode is not None else None,
                "hints": hints or [],
                "finished_at": finished_at,
                "finished_monotonic": now,
                "duration_seconds": round(now - started, 3),
                "elapsed_seconds": round(now - started, 3),
                "updated_at": finished_at,
                "stdout_preview": stdout_text[:4000],
                "stderr_preview": stderr_text[:4000],
            }
        )


def get_job_payload(job_id: str, include_output: bool = True) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return None
        snapshot = dict(job)

    stage = str(snapshot.get("stage"))
    done = stage not in {"queued", "running"}
    now = time.time()
    started = snapshot.get("started_monotonic")
    elapsed = snapshot.get("elapsed_seconds")
    if not done and started:
        elapsed = round(now - float(started), 3)

    stdout_text = str(snapshot.get("stdout", ""))
    stderr_text = str(snapshot.get("stderr", ""))
    payload = {
        "ok": bool(snapshot.get("ok")) if done else True,
        "job_id": job_id,
        "stage": stage,
        "done": done,
        "running": not done,
        "status_url": f"/jobs/{job_id}",
        "jobs_url": "/jobs",
        "poll_after_seconds": ASYNC_POLL_AFTER_SECONDS if not done else None,
        "progress_message": build_job_progress_message(snapshot, elapsed, done),
        "created_at": snapshot.get("created_at"),
        "started_at": snapshot.get("started_at"),
        "updated_at": snapshot.get("updated_at"),
        "finished_at": snapshot.get("finished_at"),
        "elapsed_seconds": elapsed,
        "duration_seconds": snapshot.get("duration_seconds"),
        "returncode": snapshot.get("returncode"),
        "error": snapshot.get("error"),
        "empty_output": bool(snapshot.get("empty_output", False)),
        "output_state": snapshot.get(
            "output_state",
            output_state(stdout_text, stderr_text),
        ),
        "process_ok": snapshot.get("process_ok"),
        "hints": snapshot.get("hints", []),
        "stdout_tail": stdout_text[-4000:],
        "stderr_tail": stderr_text[-4000:],
        "stdout_preview": snapshot.get("stdout_preview", stdout_text[:4000]),
        "stderr_preview": snapshot.get("stderr_preview", stderr_text[:4000]),
        "stdout_truncated_chars": snapshot.get("stdout_truncated_chars", 0),
        "stderr_truncated_chars": snapshot.get("stderr_truncated_chars", 0),
        "request_log": snapshot.get("request_log"),
        "repo_aliases": {k: str(v) for k, v in REPO_ALIASES.items()},
        "cwd": snapshot.get("cwd"),
        "cwd_info": snapshot.get("cwd_info"),
        "model": snapshot.get("model"),
        "approval": snapshot.get("approval"),
        "sandbox": snapshot.get("sandbox"),
        "timeout": snapshot.get("timeout"),
        "add_dirs": snapshot.get("add_dirs"),
        "skip_git_repo_check": snapshot.get("skip_git_repo_check"),
        "cmd": snapshot.get("cmd"),
    }
    if include_output and done:
        payload["stdout"] = stdout_text
        payload["stderr"] = stderr_text
    return payload


def build_job_progress_message(
    job: dict[str, Any],
    elapsed: float | None,
    done: bool,
) -> str:
    stage = str(job.get("stage"))
    if done:
        if stage == "empty_output":
            return "Codex exited successfully but produced no stdout or stderr. Treat this as no usable answer."
        if job.get("ok"):
            return f"Codex job completed in {job.get('duration_seconds')} seconds."
        return f"Codex job ended at stage '{stage}'."
    elapsed_text = f"{elapsed:.1f}" if isinstance(elapsed, (int, float)) else "0.0"
    if not str(job.get("stdout", "")).strip() and not str(job.get("stderr", "")).strip():
        return f"Codex is still {stage}; no stdout/stderr yet; elapsed {elapsed_text} seconds. Poll {ASYNC_POLL_AFTER_SECONDS}s later."
    return f"Codex is still {stage}; elapsed {elapsed_text} seconds. Poll {ASYNC_POLL_AFTER_SECONDS}s later."


def list_jobs_payload() -> dict[str, Any]:
    prune_old_jobs()
    with JOBS_LOCK:
        job_ids = sorted(
            JOBS,
            key=lambda item: str(JOBS[item].get("created_at", "")),
            reverse=True,
        )
    jobs = []
    for job_id in job_ids:
        payload = get_job_payload(job_id, include_output=False)
        if payload is not None:
            jobs.append(payload)
    return {
        "ok": True,
        "time": now_iso(),
        "count": len(job_ids),
        "retention_seconds": ASYNC_JOB_RETENTION_SECONDS,
        "jobs": jobs,
    }


def job_count() -> int:
    with JOBS_LOCK:
        return len(JOBS)
