from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from .config import (
    COMPOSE_CMD_TIMEOUT,
    COMPOSE_FILE,
    COMPOSE_INCLUDE_ALL_PROFILES,
    COMPOSE_PROFILE,
    DOCKER_CMD,
    FORWARDER_TELEGRAM_BOT_TOKEN,
    FORWARDER_TELEGRAM_CHAT_ID,
    SERVICE_RECREATE_DEFAULT_POLL_SECONDS,
    SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT,
)
from .utils import now_iso, safe_decode

SERVICE_JOBS: dict[str, dict[str, Any]] = {}
SERVICE_JOBS_LOCK = threading.Lock()


def _service_job_snapshot(job_id: str) -> dict[str, Any] | None:
    with SERVICE_JOBS_LOCK:
        job = SERVICE_JOBS.get(job_id)
        if not job:
            return None
        return dict(job)


def _set_service_job(job_id: str, **changes: Any) -> None:
    with SERVICE_JOBS_LOCK:
        job = SERVICE_JOBS.get(job_id)
        if not job:
            return
        job.update(changes)


def _append_service_job_log(job_id: str, message: str) -> None:
    line = f"[{now_iso()}] {message}"
    with SERVICE_JOBS_LOCK:
        job = SERVICE_JOBS.get(job_id)
        if not job:
            return
        logs = list(job.get("logs", []))
        logs.append(line)
        job["logs"] = logs[-200:]
        job["updated_at"] = now_iso()


def service_job_count() -> int:
    with SERVICE_JOBS_LOCK:
        return len(SERVICE_JOBS)


def list_service_jobs_payload() -> dict[str, Any]:
    with SERVICE_JOBS_LOCK:
        job_ids = sorted(
            SERVICE_JOBS,
            key=lambda item: str(SERVICE_JOBS[item].get("created_at", "")),
            reverse=True,
        )
    jobs = []
    for job_id in job_ids:
        payload = get_service_job_payload(job_id, include_logs=False)
        if payload is not None:
            jobs.append(payload)
    return {
        "ok": True,
        "time": now_iso(),
        "count": len(jobs),
        "jobs": jobs,
    }


def get_service_job_payload(
    job_id: str,
    include_logs: bool = True,
) -> dict[str, Any] | None:
    snapshot = _service_job_snapshot(job_id)
    if snapshot is None:
        return None
    done = bool(snapshot.get("done"))
    payload = {
        "ok": bool(snapshot.get("ok")) if done else True,
        "job_id": job_id,
        "job_type": "compose_service_action",
        "done": done,
        "running": not done,
        "stage": snapshot.get("stage"),
        "action": snapshot.get("action"),
        "service": snapshot.get("service"),
        "requested_service": snapshot.get("requested_service"),
        "status_url": f"/service-jobs/{job_id}",
        "created_at": snapshot.get("created_at"),
        "updated_at": snapshot.get("updated_at"),
        "started_at": snapshot.get("started_at"),
        "finished_at": snapshot.get("finished_at"),
        "duration_seconds": snapshot.get("duration_seconds"),
        "returncode": snapshot.get("returncode"),
        "error": snapshot.get("error"),
        "compose_file": str(COMPOSE_FILE),
        "wait_for_url": snapshot.get("wait_for_url"),
        "wait_timeout": snapshot.get("wait_timeout"),
        "poll_seconds": snapshot.get("poll_seconds"),
        "notify": snapshot.get("notify"),
        "notification_results": snapshot.get("notification_results", []),
        "stdout_preview": snapshot.get("stdout_preview", ""),
        "stderr_preview": snapshot.get("stderr_preview", ""),
        "request_log": snapshot.get("request_log"),
    }
    if include_logs:
        payload["logs"] = snapshot.get("logs", [])
        payload["stdout"] = snapshot.get("stdout", "")
        payload["stderr"] = snapshot.get("stderr", "")
    return payload


def _send_webhook_notification(
    url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read().decode("utf-8", errors="replace")
        return {
            "channel": "webhook",
            "url": url,
            "ok": 200 <= response.status < 300,
            "status": response.status,
            "body_preview": body[:1000],
        }


def _send_telegram_notification(text: str) -> dict[str, Any]:
    token = FORWARDER_TELEGRAM_BOT_TOKEN.strip()
    chat_id = FORWARDER_TELEGRAM_CHAT_ID.strip()
    if not token or not chat_id:
        return {
            "channel": "telegram",
            "ok": False,
            "error": "Telegram token/chat_id not configured.",
        }
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read().decode("utf-8", errors="replace")
        return {
            "channel": "telegram",
            "ok": 200 <= response.status < 300,
            "status": response.status,
            "body_preview": body[:1000],
        }


def _service_notify_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(snapshot.get("ok")),
        "job_id": snapshot.get("job_id"),
        "job_type": "compose_service_action",
        "action": snapshot.get("action"),
        "service": snapshot.get("service"),
        "requested_service": snapshot.get("requested_service"),
        "stage": snapshot.get("stage"),
        "error": snapshot.get("error"),
        "returncode": snapshot.get("returncode"),
        "finished_at": snapshot.get("finished_at"),
        "duration_seconds": snapshot.get("duration_seconds"),
        "wait_for_url": snapshot.get("wait_for_url"),
    }


def _finish_service_job(
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
    snapshot = _service_job_snapshot(job_id)
    started_monotonic = float(snapshot.get("started_monotonic") or time.time()) if snapshot else time.time()
    _set_service_job(
        job_id,
        ok=ok,
        done=True,
        stage=stage,
        returncode=returncode,
        error=error,
        stdout=stdout,
        stderr=stderr,
        stdout_preview=stdout[:4000],
        stderr_preview=stderr[:4000],
        finished_at=finished_at,
        updated_at=finished_at,
        duration_seconds=round(time.time() - started_monotonic, 3),
    )


def _wait_for_url(url: str, timeout: int, poll_seconds: float, job_id: str) -> tuple[bool, str | None]:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                status = getattr(response, "status", None)
                if status is not None and 200 <= status < 300:
                    _append_service_job_log(job_id, f"Health check passed: {url} ({status})")
                    return True, None
                last_error = f"Unexpected status: {status}"
        except Exception as e:
            last_error = str(e)
        time.sleep(poll_seconds)
    return False, last_error


def _default_wait_url(resolved_service: str, selected: dict[str, Any]) -> str | None:
    if resolved_service == "hermes" or str(selected.get("container_name") or "") == "hermes-agent":
        return "http://127.0.0.1:8642/health"
    for port in selected.get("published_ports", []) or []:
        host_url = str(port.get("host_url") or "").strip()
        if host_url:
            return host_url
    return None


def _notify_service_job(job_id: str) -> None:
    snapshot = _service_job_snapshot(job_id)
    if snapshot is None:
        return
    notify = snapshot.get("notify") or {}
    if not isinstance(notify, dict):
        return

    results: list[dict[str, Any]] = []
    message = str(
        notify.get("message")
        or f"Compose {snapshot.get('action')} for {snapshot.get('service')} "
        f"{'completed' if snapshot.get('ok') else 'failed'}."
    )

    if notify.get("telegram"):
        try:
            results.append(_send_telegram_notification(message))
        except Exception as e:
            results.append({"channel": "telegram", "ok": False, "error": str(e)})

    webhook_url = str(notify.get("webhook_url") or "").strip()
    if webhook_url:
        try:
            results.append(
                _send_webhook_notification(webhook_url, _service_notify_payload(snapshot))
            )
        except Exception as e:
            results.append(
                {
                    "channel": "webhook",
                    "url": webhook_url,
                    "ok": False,
                    "error": str(e),
                }
            )

    if results:
        _set_service_job(job_id, notification_results=results)


def start_service_job(
    service_name: str,
    action: str,
    options: dict[str, Any] | None = None,
    request_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    job_id = f"svc_{int(time.time() * 1000)}_{len(service_name)}"
    created_at = now_iso()
    notify = options.get("notify") if isinstance(options.get("notify"), dict) else {}
    wait_timeout = int(options.get("wait_timeout") or SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT)
    poll_seconds = float(options.get("poll_seconds") or SERVICE_RECREATE_DEFAULT_POLL_SECONDS)
    wait_for_url = options.get("wait_for_url")
    with SERVICE_JOBS_LOCK:
        SERVICE_JOBS[job_id] = {
            "job_id": job_id,
            "job_type": "compose_service_action",
            "requested_service": service_name,
            "service": None,
            "action": action,
            "ok": None,
            "done": False,
            "stage": "queued",
            "created_at": created_at,
            "updated_at": created_at,
            "started_at": None,
            "finished_at": None,
            "started_monotonic": None,
            "duration_seconds": None,
            "returncode": None,
            "error": None,
            "stdout": "",
            "stderr": "",
            "stdout_preview": "",
            "stderr_preview": "",
            "logs": [],
            "wait_for_url": wait_for_url,
            "wait_timeout": wait_timeout,
            "poll_seconds": poll_seconds,
            "notify": notify,
            "request_log": request_log,
            "clean": bool(options.get("clean", True)),
            "no_deps": bool(options.get("no_deps", True)),
        }
    thread = threading.Thread(
        target=run_service_job,
        args=(job_id,),
        daemon=True,
    )
    thread.start()
    return get_service_job_payload(job_id) or {"ok": False, "error": "job_not_found"}


def run_service_job(job_id: str) -> None:
    snapshot = _service_job_snapshot(job_id)
    if snapshot is None:
        return
    action = str(snapshot.get("action") or "").strip().lower()
    requested_service = str(snapshot.get("requested_service") or "")
    _set_service_job(
        job_id,
        stage="running",
        started_at=now_iso(),
        started_monotonic=time.time(),
    )
    _append_service_job_log(job_id, f"Starting {action} for requested service '{requested_service}'")

    base_snapshot = compose_services_snapshot(include_runtime=False)
    if not base_snapshot.get("ok"):
        _finish_service_job(
            job_id,
            ok=False,
            stage="compose_discovery_failed",
            error=str(base_snapshot.get("error") or "docker compose discovery failed"),
        )
        _notify_service_job(job_id)
        return

    services = base_snapshot.get("services", [])
    resolved = find_service_by_name_or_container(requested_service, services)
    if not resolved:
        _finish_service_job(
            job_id,
            ok=False,
            stage="validate_service",
            error=f"Unknown compose service: {requested_service}",
        )
        _notify_service_job(job_id)
        return

    selected = next((row for row in services if row.get("name") == resolved), {})
    wait_for_url = str(snapshot.get("wait_for_url") or "").strip() or _default_wait_url(resolved, selected)
    _set_service_job(job_id, service=resolved, wait_for_url=wait_for_url or None)
    _append_service_job_log(job_id, f"Resolved service '{requested_service}' to '{resolved}'")

    if action != "recreate":
        result = compose_service_action(resolved, action)
        _finish_service_job(
            job_id,
            ok=bool(result.get("ok")),
            stage=str(result.get("stage") or f"{action}_completed"),
            returncode=result.get("returncode"),
            error=result.get("error"),
            stdout=str(result.get("stdout") or ""),
            stderr=str(result.get("stderr") or ""),
        )
        _notify_service_job(job_id)
        return

    clean = bool(snapshot.get("clean"))
    no_deps = bool(snapshot.get("no_deps"))
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    try:
        if clean:
            rm_args = ["rm", "-f", "-s", resolved]
            _append_service_job_log(job_id, f"Running docker compose {' '.join(rm_args)}")
            rm_proc = run_docker_compose(rm_args, timeout=COMPOSE_CMD_TIMEOUT)
            stdout_parts.append(safe_decode(rm_proc.stdout))
            stderr_parts.append(safe_decode(rm_proc.stderr))
            if rm_proc.returncode != 0:
                _finish_service_job(
                    job_id,
                    ok=False,
                    stage="recreate_rm_failed",
                    returncode=rm_proc.returncode,
                    error=f"docker compose rm failed for {resolved}",
                    stdout="".join(stdout_parts),
                    stderr="".join(stderr_parts),
                )
                _notify_service_job(job_id)
                return

        up_args = ["up", "-d", "--force-recreate"]
        if no_deps:
            up_args.append("--no-deps")
        up_args.append(resolved)
        _append_service_job_log(job_id, f"Running docker compose {' '.join(up_args)}")
        up_proc = run_docker_compose(up_args, timeout=COMPOSE_CMD_TIMEOUT)
        stdout_parts.append(safe_decode(up_proc.stdout))
        stderr_parts.append(safe_decode(up_proc.stderr))
        if up_proc.returncode != 0:
            _finish_service_job(
                job_id,
                ok=False,
                stage="recreate_up_failed",
                returncode=up_proc.returncode,
                error=f"docker compose up failed for {resolved}",
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
            )
            _notify_service_job(job_id)
            return

        if wait_for_url:
            _append_service_job_log(job_id, f"Waiting for health URL {wait_for_url}")
            ready, wait_error = _wait_for_url(
                wait_for_url,
                int(snapshot.get("wait_timeout") or SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT),
                float(snapshot.get("poll_seconds") or SERVICE_RECREATE_DEFAULT_POLL_SECONDS),
                job_id,
            )
            if not ready:
                _finish_service_job(
                    job_id,
                    ok=False,
                    stage="recreate_wait_failed",
                    error=(
                        f"Service recreated but did not become healthy at {wait_for_url}: "
                        f"{wait_error}"
                    ),
                    stdout="".join(stdout_parts),
                    stderr="".join(stderr_parts),
                )
                _notify_service_job(job_id)
                return

        _finish_service_job(
            job_id,
            ok=True,
            stage="recreate_completed",
            returncode=0,
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
        )
    except subprocess.TimeoutExpired as e:
        _finish_service_job(
            job_id,
            ok=False,
            stage="recreate_timeout",
            error=str(e),
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
        )
    except Exception as e:
        _finish_service_job(
            job_id,
            ok=False,
            stage="recreate_launch_failed",
            error=str(e),
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
        )

    _notify_service_job(job_id)


def docker_compose_base_cmd() -> list[str]:
    cmd = [DOCKER_CMD, "compose", "-f", str(COMPOSE_FILE)]
    if COMPOSE_INCLUDE_ALL_PROFILES:
        cmd += ["--profile", COMPOSE_PROFILE]
    return cmd


def run_docker_compose(
    args: list[str],
    timeout: int = COMPOSE_CMD_TIMEOUT,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        docker_compose_base_cmd() + args,
        capture_output=True,
        text=False,
        timeout=timeout,
        shell=False,
    )


def parse_ps_output(stdout_text: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    payload = stdout_text.strip()
    if not payload:
        return records

    rows: list[dict[str, Any]] = []
    if payload.startswith("["):
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, list):
                rows = [row for row in parsed if isinstance(row, dict)]
        except Exception:
            return records
    else:
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)

    for row in rows:
        service = str(row.get("Service", "")).strip()
        if not service:
            continue
        records[service] = {
            "state": row.get("State"),
            "status": row.get("Status"),
            "health": row.get("Health"),
            "container_id": row.get("ID"),
            "container_name": row.get("Name") or row.get("Names"),
            "running_for": row.get("RunningFor"),
        }
    return records


def service_ports(service_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    for row in service_cfg.get("ports", []) or []:
        if not isinstance(row, dict):
            continue
        protocol = str(row.get("protocol", "tcp")).lower()
        published = row.get("published")
        target = row.get("target")
        host_url = None
        if published not in {None, ""} and protocol == "tcp":
            host_url = f"http://127.0.0.1:{published}"
        ports.append(
            {
                "published": published,
                "target": target,
                "protocol": protocol,
                "mode": row.get("mode"),
                "host_url": host_url,
            }
        )
    return ports


def compose_services_snapshot(
    include_runtime: bool = True,
) -> dict[str, Any]:
    cmd_base = docker_compose_base_cmd()
    payload: dict[str, Any] = {
        "ok": False,
        "time": now_iso(),
        "compose_file": str(COMPOSE_FILE),
        "compose_file_exists": COMPOSE_FILE.exists(),
        "docker_cmd": DOCKER_CMD,
        "include_all_profiles": COMPOSE_INCLUDE_ALL_PROFILES,
        "profile": COMPOSE_PROFILE if COMPOSE_INCLUDE_ALL_PROFILES else None,
        "cmd_base": cmd_base,
        "service_count": 0,
        "service_names": [],
        "services": [],
    }
    if not COMPOSE_FILE.exists():
        payload["error"] = f"Compose file not found: {COMPOSE_FILE}"
        return payload

    try:
        config_proc = run_docker_compose(["config", "--format", "json"])
    except subprocess.TimeoutExpired:
        payload["error"] = (
            "docker compose config timed out after "
            f"{COMPOSE_CMD_TIMEOUT} seconds."
        )
        return payload
    except FileNotFoundError:
        payload["error"] = f"Docker command not found: {DOCKER_CMD}"
        return payload
    except Exception as e:
        payload["error"] = str(e)
        return payload

    config_stdout = safe_decode(config_proc.stdout)
    config_stderr = safe_decode(config_proc.stderr)
    payload["config"] = {
        "returncode": config_proc.returncode,
        "stderr_preview": config_stderr[:4000],
    }
    if config_proc.returncode != 0:
        payload["error"] = "docker compose config failed"
        payload["config"]["stdout_preview"] = config_stdout[:4000]
        return payload

    try:
        config_json = json.loads(config_stdout)
    except Exception as e:
        payload["error"] = f"Failed to parse compose config JSON: {e}"
        payload["config"]["stdout_preview"] = config_stdout[:4000]
        return payload

    services_cfg = config_json.get("services", {})
    if not isinstance(services_cfg, dict):
        payload["error"] = "Unexpected compose config format: missing services map."
        return payload

    runtime_by_service: dict[str, dict[str, Any]] = {}
    if include_runtime:
        try:
            ps_proc = run_docker_compose(["ps", "--format", "json"])
            ps_stdout = safe_decode(ps_proc.stdout)
            ps_stderr = safe_decode(ps_proc.stderr)
            payload["runtime"] = {
                "returncode": ps_proc.returncode,
                "stderr_preview": ps_stderr[:4000],
            }
            if ps_proc.returncode == 0:
                runtime_by_service = parse_ps_output(ps_stdout)
            else:
                payload["runtime_error"] = "docker compose ps failed"
                payload["runtime"]["stdout_preview"] = ps_stdout[:4000]
        except subprocess.TimeoutExpired:
            payload["runtime_error"] = (
                "docker compose ps timed out after "
                f"{COMPOSE_CMD_TIMEOUT} seconds."
            )
        except Exception as e:
            payload["runtime_error"] = str(e)

    services: list[dict[str, Any]] = []
    for service_name in sorted(services_cfg.keys()):
        service_cfg = services_cfg.get(service_name) or {}
        runtime = runtime_by_service.get(service_name, {})
        ports = service_ports(service_cfg)
        services.append(
            {
                "name": service_name,
                "container_name": service_cfg.get("container_name"),
                "profiles": service_cfg.get("profiles", []),
                "published_ports": ports,
                "has_published_port": any(
                    port.get("published") not in {None, ""}
                    for port in ports
                ),
                "state": runtime.get("state"),
                "status": runtime.get("status"),
                "health": runtime.get("health"),
                "running_for": runtime.get("running_for"),
                "container_id": runtime.get("container_id"),
                "runtime_container_name": runtime.get("container_name"),
            }
        )

    payload["services"] = services
    payload["service_names"] = [row["name"] for row in services]
    payload["service_count"] = len(services)
    payload["ok"] = True
    return payload


def find_service_by_name_or_container(
    requested: str,
    services: list[dict[str, Any]],
) -> str | None:
    wanted = requested.strip().lower()
    if not wanted:
        return None
    for row in services:
        if str(row.get("name", "")).strip().lower() == wanted:
            return str(row["name"])
    for row in services:
        container_name = str(row.get("container_name") or "").strip().lower()
        runtime_name = str(row.get("runtime_container_name") or "").strip().lower()
        if wanted and wanted in {container_name, runtime_name}:
            return str(row["name"])
    return None


def compose_service_details_payload(
    service_name: str,
    include_runtime: bool = True,
) -> dict[str, Any]:
    snapshot = compose_services_snapshot(include_runtime=include_runtime)
    if not snapshot.get("ok"):
        return snapshot
    services = snapshot.get("services", [])
    resolved = find_service_by_name_or_container(service_name, services)
    if not resolved:
        return {
            "ok": False,
            "error": f"Unknown compose service: {service_name}",
            "requested_service": service_name,
            "known_services": snapshot.get("service_names", []),
            "time": now_iso(),
            "compose_file": str(COMPOSE_FILE),
        }
    details = next(
        (row for row in services if row.get("name") == resolved),
        None,
    )
    return {
        "ok": True,
        "time": now_iso(),
        "compose_file": str(COMPOSE_FILE),
        "requested_service": service_name,
        "service": resolved,
        "details": details,
    }


def compose_service_action(
    service_name: str,
    action: str,
    timeout: int = COMPOSE_CMD_TIMEOUT,
) -> dict[str, Any]:
    action = action.strip().lower()
    if action not in {"restart", "start", "stop"}:
        return {
            "ok": False,
            "stage": "validate_action",
            "error": f"Unsupported compose action: {action}",
            "supported_actions": ["restart", "start", "stop"],
            "requested_service": service_name,
            "time": now_iso(),
        }

    snapshot = compose_services_snapshot(include_runtime=False)
    if not snapshot.get("ok"):
        snapshot["stage"] = "compose_discovery_failed"
        snapshot["action"] = action
        return snapshot

    services = snapshot.get("services", [])
    resolved = find_service_by_name_or_container(service_name, services)
    if not resolved:
        return {
            "ok": False,
            "stage": "validate_service",
            "error": f"Unknown compose service: {service_name}",
            "action": action,
            "requested_service": service_name,
            "known_services": snapshot.get("service_names", []),
            "compose_file": str(COMPOSE_FILE),
            "time": now_iso(),
        }

    selected = next((row for row in services if row.get("name") == resolved), {})
    cmd = docker_compose_base_cmd() + [action, resolved]
    try:
        proc = run_docker_compose([action, resolved], timeout=timeout)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stage": f"{action}_timeout",
            "error": f"docker compose {action} timed out after {timeout} seconds.",
            "action": action,
            "requested_service": service_name,
            "service": resolved,
            "cmd": cmd,
            "compose_file": str(COMPOSE_FILE),
            "time": now_iso(),
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "stage": f"{action}_launch",
            "error": f"Docker command not found: {DOCKER_CMD}",
            "action": action,
            "requested_service": service_name,
            "service": resolved,
            "cmd": cmd,
            "compose_file": str(COMPOSE_FILE),
            "time": now_iso(),
        }
    except Exception as e:
        return {
            "ok": False,
            "stage": f"{action}_launch",
            "error": str(e),
            "action": action,
            "requested_service": service_name,
            "service": resolved,
            "cmd": cmd,
            "compose_file": str(COMPOSE_FILE),
            "time": now_iso(),
        }

    stdout_text = safe_decode(proc.stdout)
    stderr_text = safe_decode(proc.stderr)
    success = proc.returncode == 0
    return {
        "ok": success,
        "stage": f"{action}_completed" if success else f"{action}_failed",
        "action": action,
        "time": now_iso(),
        "requested_service": service_name,
        "service": resolved,
        "container_name": selected.get("container_name"),
        "compose_file": str(COMPOSE_FILE),
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_preview": stdout_text[:4000],
        "stderr_preview": stderr_text[:4000],
    }


def restart_compose_service(
    service_name: str,
    timeout: int = COMPOSE_CMD_TIMEOUT,
) -> dict[str, Any]:
    return compose_service_action(service_name, "restart", timeout)


def start_compose_service(
    service_name: str,
    timeout: int = COMPOSE_CMD_TIMEOUT,
) -> dict[str, Any]:
    return compose_service_action(service_name, "start", timeout)


def stop_compose_service(
    service_name: str,
    timeout: int = COMPOSE_CMD_TIMEOUT,
) -> dict[str, Any]:
    return compose_service_action(service_name, "stop", timeout)


def parse_service_path(path: str, prefix: str) -> str | None:
    if not path.startswith(prefix):
        return None
    value = path.removeprefix(prefix).strip()
    if not value:
        return None
    if "/" in value:
        return None
    return value
