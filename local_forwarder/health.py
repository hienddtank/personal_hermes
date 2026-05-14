from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .compose import compose_services_snapshot
from .compose import service_job_count
from .bridge import list_winbridge_jobs_payload
from .config import (
    ALLOWED_ROOTS,
    ASYNC_JOB_RETENTION_SECONDS,
    ASYNC_OUTPUT_LIMIT_CHARS,
    ASYNC_POLL_AFTER_SECONDS,
    CODEX_CMD,
    COMPOSE_CMD_TIMEOUT,
    COMPOSE_FILE,
    COMPOSE_INCLUDE_ALL_PROFILES,
    COMPOSE_PROFILE,
    DEFAULT_APPROVAL,
    DEFAULT_MODEL,
    DEFAULT_RUN_KEEPALIVE,
    DEFAULT_RUN_KEEPALIVE_SECONDS,
    DEFAULT_SANDBOX,
    DEFAULT_SKIP_GIT_REPO_CHECK,
    DEFAULT_TIMEOUT,
    DOCKER_CMD,
    HOST,
    LOG_DIR,
    PORT,
    REPO_ALIASES,
    FORWARDER_TELEGRAM_CHAT_ID,
    FORWARDER_TELEGRAM_BOT_TOKEN,
    SERVICE_RECREATE_DEFAULT_POLL_SECONDS,
    SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT,
    WINBRIDGE_ALLOWED_SCRIPT_ROOTS,
    WINBRIDGE_ALLOWED_SHELLS,
    WINBRIDGE_DEFAULT_TIMEOUT,
)
from .jobs import job_count
from .request_logging import request_log_config
from .utils import now_iso


def build_health() -> dict[str, Any]:
    compose_snapshot = compose_services_snapshot(include_runtime=False)
    return {
        "ok": True,
        "service": "codex-forwarder",
        "time": now_iso(),
        "host": HOST,
        "port": PORT,
        "codex_cmd": CODEX_CMD,
        "codex_cmd_exists": Path(CODEX_CMD).exists(),
        "node_in_path": shutil.which("node"),
        "cmd_in_path": shutil.which("cmd"),
        "docker_cmd": DOCKER_CMD,
        "docker_in_path": shutil.which(DOCKER_CMD),
        "allowed_roots": [str(x) for x in ALLOWED_ROOTS],
        "repo_aliases": {k: str(v) for k, v in REPO_ALIASES.items()},
        "defaults": {
            "model": DEFAULT_MODEL,
            "approval": DEFAULT_APPROVAL,
            "sandbox": DEFAULT_SANDBOX,
            "timeout": DEFAULT_TIMEOUT,
            "skip_git_repo_check": DEFAULT_SKIP_GIT_REPO_CHECK,
            "run_keep_alive": DEFAULT_RUN_KEEPALIVE,
            "run_keep_alive_seconds": DEFAULT_RUN_KEEPALIVE_SECONDS,
        },
        "request_logs": {
            **request_log_config(),
            "exists": LOG_DIR.exists(),
        },
        "compose": {
            "compose_file": str(COMPOSE_FILE),
            "compose_file_exists": COMPOSE_FILE.exists(),
            "include_all_profiles": COMPOSE_INCLUDE_ALL_PROFILES,
            "profile": COMPOSE_PROFILE if COMPOSE_INCLUDE_ALL_PROFILES else None,
            "timeout_seconds": COMPOSE_CMD_TIMEOUT,
            "recreate_default_wait_timeout": SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT,
            "recreate_default_poll_seconds": SERVICE_RECREATE_DEFAULT_POLL_SECONDS,
            "telegram_configured": bool(
                FORWARDER_TELEGRAM_BOT_TOKEN and FORWARDER_TELEGRAM_CHAT_ID
            ),
            "service_count": compose_snapshot.get("service_count"),
            "service_names": compose_snapshot.get("service_names"),
            "discovery_ok": compose_snapshot.get("ok"),
            "discovery_error": compose_snapshot.get("error"),
            "config_returncode": (compose_snapshot.get("config") or {}).get("returncode"),
            "config_stderr_preview": (
                (compose_snapshot.get("config") or {}).get("stderr_preview") or ""
            )[:1000],
        },
        "async_jobs": {
            "active_or_recent": job_count(),
            "service_actions": service_job_count(),
            "winbridge": list_winbridge_jobs_payload().get("count"),
            "retention_seconds": ASYNC_JOB_RETENTION_SECONDS,
            "output_limit_chars": ASYNC_OUTPUT_LIMIT_CHARS,
            "poll_after_seconds": ASYNC_POLL_AFTER_SECONDS,
        },
        "winbridge": {
            "default_timeout": WINBRIDGE_DEFAULT_TIMEOUT,
            "allowed_shells": sorted(WINBRIDGE_ALLOWED_SHELLS),
            "allowed_script_roots": [str(x) for x in WINBRIDGE_ALLOWED_SCRIPT_ROOTS],
            "note": "WinBridge runs directly on the Windows host and does not use codex exec sandboxing.",
        },
        "run_keepalive": {
            "enabled": DEFAULT_RUN_KEEPALIVE,
            "interval_seconds": DEFAULT_RUN_KEEPALIVE_SECONDS,
            "body_format": "leading JSON whitespace heartbeats followed by one final JSON object",
            "headers": [
                "X-Forwarder-Keepalive",
                "X-Forwarder-Job-Id",
                "X-Forwarder-Status-Url",
            ],
        },
        "routes": {
            "GET /": "help guide",
            "GET /help": "help guide",
            "GET /health": "health and diagnostics",
            "GET /jobs": "list recent background Codex jobs",
            "GET /jobs/{job_id}": "poll background Codex progress and final output",
            "GET /winbridge/jobs": "list recent background WinBridge jobs",
            "GET /winbridge/jobs/{job_id}": "poll background WinBridge status and output",
            "GET /service-jobs": "list recent async compose service jobs",
            "GET /service-jobs/{job_id}": "poll async compose service job status",
            "GET /services": "discover compose services",
            "GET /services/{service}": "service details",
            "GET /openapi.json": "OpenAPI document",
            "POST /winbridge/run": "run an allowed Windows PowerShell script directly on the host",
            "POST /winbridge/run-async": "start an allowed Windows PowerShell script directly on the host",
            "POST /run": "run codex exec",
            "POST /run-async": "start codex exec and return a job_id immediately",
            "POST /services/{service}/recreate": "clean recreate one compose service asynchronously",
            "POST /services/{service}/start": "start one compose service container",
            "POST /services/{service}/stop": "stop one compose service container",
            "POST /services/{service}/restart": "restart one compose service container",
            "POST /services/recreate": "clean recreate one compose service from JSON body asynchronously",
            "POST /services/start": "start one compose service from JSON body",
            "POST /services/stop": "stop one compose service from JSON body",
            "POST /services/restart": "restart one compose service from JSON body",
        },
        "examples": {
            "health": "curl http://127.0.0.1:8768/health",
            "jobs": "curl http://127.0.0.1:8768/jobs",
            "winbridge_jobs": "curl http://127.0.0.1:8768/winbridge/jobs",
            "service_jobs": "curl http://127.0.0.1:8768/service-jobs",
            "services": "curl http://127.0.0.1:8768/services",
            "service_details": "curl http://127.0.0.1:8768/services/hermes",
            "run_restart_ps1": (
                "curl -X POST http://127.0.0.1:8768/winbridge/run-async "
                "-H \"Content-Type: application/json\" "
                "-d '{\"script\":\"D:/mkt/python/hermes/workspace/scripts/docker-restart.ps1\",\"cwd\":\"D:/mkt/python/hermes\",\"timeout\":300}'"
            ),
            "recreate_service": (
                "curl -X POST http://127.0.0.1:8768/services/hermes/recreate "
                "-H \"Content-Type: application/json\" "
                "-d '{\"wait_for_url\":\"http://127.0.0.1:8642/health\",\"notify\":{\"telegram\":true}}'"
            ),
            "start_service": "curl -X POST http://127.0.0.1:8768/services/hermes/start",
            "stop_service": "curl -X POST http://127.0.0.1:8768/services/hermes/stop",
            "restart_service": "curl -X POST http://127.0.0.1:8768/services/hermes/restart",
            "start_service_with_json": (
                "curl -X POST http://127.0.0.1:8768/services/start "
                "-H \"Content-Type: application/json\" "
                "-d '{\"service\":\"hermes\"}'"
            ),
            "stop_service_with_json": (
                "curl -X POST http://127.0.0.1:8768/services/stop "
                "-H \"Content-Type: application/json\" "
                "-d '{\"service\":\"hermes\"}'"
            ),
            "restart_service_with_json": (
                "curl -X POST http://127.0.0.1:8768/services/restart "
                "-H \"Content-Type: application/json\" "
                "-d '{\"service\":\"hermes\"}'"
            ),
            "recreate_service_with_json": (
                "curl -X POST http://127.0.0.1:8768/services/recreate "
                "-H \"Content-Type: application/json\" "
                "-d '{\"service\":\"hermes\",\"notify\":{\"telegram\":true}}'"
            ),
            "run_with_repo_alias": {
                "repo": "fish_doc_extractor",
                "prompt": "Summarize this repository and identify one documentation gap.",
                "model": DEFAULT_MODEL,
                "approval": DEFAULT_APPROVAL,
                "sandbox": DEFAULT_SANDBOX,
                "timeout": DEFAULT_TIMEOUT,
            },
            "run_with_cwd": {
                "cwd": r"D:\mkt\python\Fish_Doc_Extractor",
                "prompt": "Summarize this repository and identify one documentation gap.",
                "model": DEFAULT_MODEL,
                "approval": DEFAULT_APPROVAL,
                "sandbox": DEFAULT_SANDBOX,
                "timeout": DEFAULT_TIMEOUT,
            },
            "run_async_with_repo_alias": {
                "repo": "fish_doc_extractor",
                "prompt": "Summarize this repository and identify one documentation gap.",
                "model": DEFAULT_MODEL,
                "approval": DEFAULT_APPROVAL,
                "sandbox": DEFAULT_SANDBOX,
                "timeout": DEFAULT_TIMEOUT,
                "poll": "GET /jobs/{job_id}",
            },
        },
        "notes": [
            "This service does not require an interactive Codex terminal window.",
            "It launches a fresh 'codex exec' process per request.",
            "Compose service discovery is dynamic and reloads from docker-compose for each request.",
            "Use POST /services/{service}/{start|stop|restart|recreate} with either service name or container_name.",
            "Use POST /winbridge/run-async for host PowerShell scripts; this bypasses codex exec sandboxing but still inherits the Windows account permissions of the forwarder process.",
            "Use POST /run-async for long-running tasks so callers can poll progress.",
            "Use POST /services/{service}/recreate for self-restarts because it runs on the host and can wait for Hermes to come back before notifying.",
            "POST /run keeps the HTTP response active with whitespace heartbeats until the final JSON result is ready.",
            "Use 'repo' aliases whenever possible to reduce path errors.",
            "If a request fails, inspect 'stage', 'error', 'stderr_preview', and 'cmd' first.",
            "If stage is 'empty_output', the Codex process exited 0 but returned no usable answer.",
        ],
    }
