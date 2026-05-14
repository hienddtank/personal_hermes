from __future__ import annotations

import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from .codex import (
    build_run_result_payload,
    parse_run_payload,
    validation_error_context,
)
from .bridge import (
    build_winbridge_result_payload,
    get_winbridge_job_payload,
    list_winbridge_jobs_payload,
    parse_winbridge_payload,
    start_winbridge_job,
)
from .compose import (
    compose_service_action,
    compose_service_details_payload,
    compose_services_snapshot,
    get_service_job_payload,
    list_service_jobs_payload,
    parse_service_path,
    start_service_job,
)
from .config import (
    ASYNC_JOB_RETENTION_SECONDS,
    CODEX_CMD,
    DEFAULT_RUN_KEEPALIVE,
    DEFAULT_RUN_KEEPALIVE_SECONDS,
)
from .docs import build_help, build_openapi
from .health import build_health
from .jobs import get_job_payload, list_jobs_payload, start_codex_job
from .request_logging import save_request_log
from .utils import now_iso, route_path, safe_decode


class Handler(BaseHTTPRequestHandler):
    server_version = "CodexForwarder/1.6"

    def _send_json(
        self,
        code: int,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_run_keepalive_response(
        self,
        config: dict[str, Any],
        request_log: dict[str, Any] | None,
    ) -> None:
        job = start_codex_job(config, request_log)
        job_id = str(job.get("job_id") or "")
        status_url = str(job.get("status_url") or f"/jobs/{job_id}")
        keep_alive_seconds = float(
            config.get("keep_alive_seconds", DEFAULT_RUN_KEEPALIVE_SECONDS)
        )

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Forwarder-Keepalive", str(keep_alive_seconds))
        if job_id:
            self.send_header("X-Forwarder-Job-Id", job_id)
            self.send_header("X-Forwarder-Status-Url", status_url)
        self.end_headers()
        self.close_connection = True

        next_heartbeat = 0.0
        try:
            while True:
                status = get_job_payload(job_id) if job_id else None
                if not status:
                    status = {
                        "ok": False,
                        "stage": "job_not_found",
                        "error": f"Unknown or expired job: {job_id}",
                        "job_id": job_id,
                        "status_url": status_url,
                        "time": now_iso(),
                    }
                    self._write_streamed_json(status)
                    return

                if status.get("done"):
                    status["blocking_keepalive"] = True
                    status["keep_alive_seconds"] = keep_alive_seconds
                    status["time"] = now_iso()
                    self._write_streamed_json(status)
                    return

                now = time.time()
                if now >= next_heartbeat:
                    # JSON-safe whitespace keeps idle HTTP clients from timing out.
                    self.wfile.write(b"\n")
                    self.wfile.flush()
                    next_heartbeat = now + keep_alive_seconds

                time.sleep(min(1.0, keep_alive_seconds))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            logger_message = (
                f"[{now_iso()}] client disconnected while waiting for {job_id}; "
                f"job remains available at {status_url}"
            )
            print(logger_message)

    def _write_streamed_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def _read_request_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length < 0:
            raise ValueError("Content-Length cannot be negative.")
        return self.rfile.read(content_length)

    def _log_request_payload(
        self,
        raw_body: bytes | None = None,
        stage: str = "received",
        error: str | None = None,
    ) -> dict[str, Any]:
        log_info = save_request_log(self, raw_body, stage, error)
        self.request_log_info = log_info
        return log_info

    def _send_help(
        self,
        code: int = 200,
        error: str | None = None,
        original_status: int | None = None,
    ) -> None:
        headers = None
        if code == 405:
            headers = {"Allow": "GET, POST, OPTIONS"}
        payload = build_help(
            requested_path=getattr(self, "path", None),
            method=getattr(self, "command", None),
            error=error,
            original_status=original_status,
        )
        log_info = getattr(self, "request_log_info", None)
        if log_info:
            payload["request_log"] = log_info
        self._send_json(
            code,
            payload,
            headers=headers,
        )

    def _error(
        self,
        code: int,
        stage: str,
        error: str,
        extra: dict[str, Any] | None = None,
        include_help: bool = False,
    ) -> None:
        payload: dict[str, Any] = {
            "ok": False,
            "stage": stage,
            "error": error,
            "time": now_iso(),
            "help_url": "/help",
        }
        if include_help:
            payload["help"] = build_help(
                requested_path=getattr(self, "path", None),
                method=getattr(self, "command", None),
            )
        log_info = getattr(self, "request_log_info", None)
        if log_info:
            payload["request_log"] = log_info
        if extra:
            payload.update(extra)
        self._send_json(code, payload)

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        error = message or self.responses.get(code, ("HTTP error",))[0]
        if not getattr(self, "request_log_info", None):
            self._log_request_payload(stage="send_error", error=error)
        response_code = 200 if code == 404 else code
        self._send_help(response_code, error, original_status=code)

    def do_GET(self) -> None:
        self._log_request_payload()
        path = route_path(self.path)

        if path in {"/", "/help"}:
            self._send_json(200, build_help())
            return

        if path == "/health":
            self._send_json(200, build_health())
            return

        if path == "/jobs":
            self._send_json(200, list_jobs_payload())
            return

        if path == "/winbridge/jobs":
            self._send_json(200, list_winbridge_jobs_payload())
            return

        if path == "/service-jobs":
            self._send_json(200, list_service_jobs_payload())
            return

        if path.startswith("/jobs/"):
            job_id = path.removeprefix("/jobs/").strip()
            payload = get_job_payload(job_id)
            if not payload:
                self._error(
                    404,
                    "job_not_found",
                    f"Unknown or expired job: {job_id}",
                    {
                        "jobs_url": "/jobs",
                        "retention_seconds": ASYNC_JOB_RETENTION_SECONDS,
                    },
                    include_help=True,
                )
                return
            self._send_json(200, payload)
            return

        if path.startswith("/winbridge/jobs/"):
            job_id = path.removeprefix("/winbridge/jobs/").strip()
            payload = get_winbridge_job_payload(job_id)
            if not payload:
                self._error(
                    404,
                    "job_not_found",
                    f"Unknown or expired winbridge job: {job_id}",
                    {
                        "jobs_url": "/winbridge/jobs",
                    },
                    include_help=True,
                )
                return
            self._send_json(200, payload)
            return

        if path.startswith("/service-jobs/"):
            job_id = path.removeprefix("/service-jobs/").strip()
            payload = get_service_job_payload(job_id)
            if not payload:
                self._error(
                    404,
                    "job_not_found",
                    f"Unknown or expired service job: {job_id}",
                    {
                        "jobs_url": "/service-jobs",
                    },
                    include_help=True,
                )
                return
            self._send_json(200, payload)
            return

        if path == "/services":
            payload = compose_services_snapshot(include_runtime=True)
            code = 200 if payload.get("ok") else 500
            self._send_json(code, payload)
            return

        service_name = parse_service_path(path, "/services/")
        if service_name:
            payload = compose_service_details_payload(service_name, include_runtime=True)
            if payload.get("ok"):
                self._send_json(200, payload)
                return
            error_text = str(payload.get("error", "")).lower()
            code = 404 if "unknown compose service" in error_text else 500
            self._send_json(code, payload)
            return

        if path == "/openapi.json":
            self._send_json(200, build_openapi())
            return

        self._send_help(200, f"Unknown GET route: {self.path}", original_status=404)

    def do_POST(self) -> None:
        request_started = time.time()

        try:
            raw = self._read_request_body()
        except Exception as e:
            self._log_request_payload(stage="read_request_failed", error=str(e))
            self._error(400, "read_request", str(e), include_help=True)
            return

        self._log_request_payload(raw)

        path = route_path(self.path)

        action_service = None
        action_name = None
        for action in ("recreate", "restart", "start", "stop"):
            suffix = f"/{action}"
            if path.startswith("/services/") and path.endswith(suffix):
                candidate = path[len("/services/") : -len(suffix)].strip()
                if candidate and "/" not in candidate:
                    action_service = candidate
                    action_name = action
                break

        if action_service and action_name:
            if action_name == "recreate":
                try:
                    data = json.loads(raw.decode("utf-8")) if raw else {}
                except Exception as e:
                    self._error(
                        400,
                        "parse_json",
                        str(e),
                        {
                            "raw_preview": raw[:500].decode("utf-8", errors="replace"),
                        },
                        include_help=True,
                    )
                    return
                payload = start_service_job(
                    action_service,
                    "recreate",
                    data if isinstance(data, dict) else {},
                    getattr(self, "request_log_info", None),
                )
                payload["started"] = True
                payload["time"] = now_iso()
                self._send_json(200, payload)
                return
            payload = compose_service_action(action_service, action_name)
            if payload.get("ok"):
                self._send_json(200, payload)
                return
            code = 404 if payload.get("stage") == "validate_service" else 500
            self._send_json(code, payload)
            return

        if path in {"/services/recreate", "/services/restart", "/services/start", "/services/stop"}:
            action_name = path.removeprefix("/services/").strip().lower()
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception as e:
                self._error(
                    400,
                    "parse_json",
                    str(e),
                    {
                        "raw_preview": raw[:500].decode("utf-8", errors="replace"),
                    },
                    include_help=True,
                )
                return
            service_name = str(data.get("service", "")).strip()
            if not service_name:
                self._error(
                    400,
                    "validate_input",
                    f"Field 'service' is required for POST {path}.",
                    {
                        "example": {"service": "hermes"},
                    },
                    include_help=True,
                )
                return
            if action_name == "recreate":
                payload = start_service_job(
                    service_name,
                    "recreate",
                    data if isinstance(data, dict) else {},
                    getattr(self, "request_log_info", None),
                )
                payload["started"] = True
                payload["time"] = now_iso()
                self._send_json(200, payload)
                return
            payload = compose_service_action(service_name, action_name)
            if payload.get("ok"):
                self._send_json(200, payload)
                return
            code = 404 if payload.get("stage") == "validate_service" else 500
            self._send_json(code, payload)
            return

        if path in {"/winbridge/run", "/winbridge/run-async"}:
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception as e:
                self._error(
                    400,
                    "parse_json",
                    str(e),
                    {
                        "raw_preview": raw[:500].decode("utf-8", errors="replace"),
                    },
                    include_help=True,
                )
                return

            try:
                config = parse_winbridge_payload(data)
            except Exception as e:
                self._error(
                    400,
                    "validate_input",
                    str(e),
                    {
                        "received": data,
                    },
                    include_help=True,
                )
                return

            if path == "/winbridge/run-async":
                payload = start_winbridge_job(
                    config,
                    getattr(self, "request_log_info", None),
                )
                payload["started"] = True
                payload["time"] = now_iso()
                self._send_json(200, payload)
                return

            try:
                proc = subprocess.run(
                    config["cmd"],
                    capture_output=True,
                    text=False,
                    timeout=config["timeout"],
                    shell=False,
                    cwd=str(config["cwd"]),
                )
            except subprocess.TimeoutExpired:
                self._error(
                    408,
                    "bridge_timeout",
                    f"WinBridge command timed out after {config['timeout']} seconds.",
                    {
                        "cmd": config["cmd"],
                        "cwd": str(config["cwd"]),
                        "duration_seconds": round(time.time() - request_started, 3),
                    },
                )
                return
            except FileNotFoundError as e:
                self._error(
                    500,
                    "bridge_launch",
                    str(e),
                    {
                        "cmd": config["cmd"],
                        "cwd": str(config["cwd"]),
                    },
                )
                return
            except Exception as e:
                self._error(
                    500,
                    "bridge_launch",
                    str(e),
                    {
                        "cmd": config["cmd"],
                        "cwd": str(config["cwd"]),
                    },
                )
                return

            stdout_text = safe_decode(proc.stdout)
            stderr_text = safe_decode(proc.stderr)
            self._send_json(
                200,
                build_winbridge_result_payload(
                    config,
                    request_started,
                    proc.returncode,
                    stdout_text,
                    stderr_text,
                    getattr(self, "request_log_info", None),
                ),
            )
            return

        if path not in {"/run", "/run-async"}:
            self._send_help(200, f"Unknown POST route: {self.path}", original_status=404)
            return

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._error(
                400,
                "parse_json",
                str(e),
                {
                    "raw_preview": raw[:500].decode("utf-8", errors="replace"),
                },
                include_help=True,
            )
            return

        try:
            config = parse_run_payload(data)
        except Exception as e:
            self._error(
                400,
                "validate_input",
                str(e),
                validation_error_context(data),
                include_help=True,
            )
            return

        if not Path(CODEX_CMD).exists():
            self._error(
                500,
                "preflight",
                f"Codex launcher not found: {CODEX_CMD}",
                {
                    "hint": "Update CODEX_CMD to the exact path of codex.cmd",
                },
            )
            return

        if path == "/run-async":
            payload = start_codex_job(config, getattr(self, "request_log_info", None))
            payload["started"] = True
            payload["time"] = now_iso()
            self._send_json(200, payload)
            return

        if config.get("keep_alive", DEFAULT_RUN_KEEPALIVE):
            self._send_run_keepalive_response(
                config,
                getattr(self, "request_log_info", None),
            )
            return

        try:
            proc = subprocess.run(
                config["cmd"],
                capture_output=True,
                text=False,
                timeout=config["timeout"],
                shell=False,
                cwd=str(config["cwd"]),
            )
        except subprocess.TimeoutExpired:
            self._error(
                408,
                "run_timeout",
                f"Codex timed out after {config['timeout']} seconds.",
                {
                    "cmd": config["cmd"],
                    "cwd": str(config["cwd"]),
                    "duration_seconds": round(time.time() - request_started, 3),
                    "hint": "Increase the timeout for larger tasks.",
                },
            )
            return
        except FileNotFoundError as e:
            self._error(
                500,
                "launch_codex",
                str(e),
                {
                    "cmd": config["cmd"],
                    "cwd": str(config["cwd"]),
                    "hint": "This usually means cmd.exe, codex.cmd, or a dependency like node could not be started.",
                },
            )
            return
        except Exception as e:
            self._error(
                500,
                "run_codex",
                str(e),
                {
                    "cmd": config["cmd"],
                    "cwd": str(config["cwd"]),
                },
            )
            return

        stdout_text = safe_decode(proc.stdout)
        stderr_text = safe_decode(proc.stderr)
        self._send_json(
            200,
            build_run_result_payload(
                config,
                request_started,
                proc.returncode,
                stdout_text,
                stderr_text,
                getattr(self, "request_log_info", None),
            ),
        )

    def do_OPTIONS(self) -> None:
        self._log_request_payload()
        self._send_json(
            200,
            {
                "ok": True,
                "time": now_iso(),
                "allow": ["GET", "POST", "OPTIONS"],
                "help": build_help(),
            },
            headers={"Allow": "GET, POST, OPTIONS"},
        )

    def _handle_unsupported_method(self) -> None:
        try:
            raw = self._read_request_body()
        except Exception as e:
            self._log_request_payload(stage="read_request_failed", error=str(e))
        else:
            self._log_request_payload(raw, stage="unsupported_method")
        self._send_help(405, f"Unsupported method: {self.command}")

    def do_DELETE(self) -> None:
        self._handle_unsupported_method()

    def do_PATCH(self) -> None:
        self._handle_unsupported_method()

    def do_PUT(self) -> None:
        self._handle_unsupported_method()

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{now_iso()}] {self.address_string()} - {format % args}")
