from __future__ import annotations

from typing import Any

from .config import (
    ALLOWED_ROOTS,
    ASYNC_JOB_RETENTION_SECONDS,
    ASYNC_POLL_AFTER_SECONDS,
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
    FORWARDER_TELEGRAM_CHAT_ID,
    FORWARDER_TELEGRAM_BOT_TOKEN,
    PORT,
    REPO_ALIASES,
    SERVICE_RECREATE_DEFAULT_POLL_SECONDS,
    SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT,
    WINBRIDGE_ALLOWED_SCRIPT_ROOTS,
    WINBRIDGE_ALLOWED_SHELLS,
    WINBRIDGE_DEFAULT_TIMEOUT,
)
from .request_logging import request_log_config
from .utils import now_iso


def build_help(
    requested_path: str | None = None,
    method: str | None = None,
    error: str | None = None,
    original_status: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": error is None,
        "service": "codex-forwarder",
        "time": now_iso(),
        "summary": (
            "HTTP wrapper around Codex CLI plus Docker Compose service control "
            "and direct Windows host script execution. "
            "Use /services to discover compose services and "
            "POST /services/{service}/{start|stop|restart|recreate} to control one service."
        ),
        "help_url": "/help",
        "progress": {
            "use": "POST /run keeps the connection alive with JSON whitespace until completion. POST /run-async returns immediately for polling.",
            "poll_after_seconds": ASYNC_POLL_AFTER_SECONDS,
            "retention_seconds": ASYNC_JOB_RETENTION_SECONDS,
            "run_keep_alive": DEFAULT_RUN_KEEPALIVE,
            "run_keep_alive_seconds": DEFAULT_RUN_KEEPALIVE_SECONDS,
            "run_keep_alive_headers": [
                "X-Forwarder-Keepalive",
                "X-Forwarder-Job-Id",
                "X-Forwarder-Status-Url",
            ],
        },
        "empty_output_behavior": {
            "stage": "empty_output",
            "ok": False,
            "meaning": "Codex exited with returncode 0 but produced no stdout or stderr.",
            "action": "Do not treat this as file content. Inspect request_log.body and retry with an explicit prompt, repo, and cwd only if needed.",
        },
        "request_logs": {
            **request_log_config(),
            "behavior": (
                "Each inbound request is logged before route validation or JSON "
                "parsing. Logs older than the retention window are deleted."
            ),
        },
        "base_urls": [
            f"http://127.0.0.1:{PORT}",
            f"http://localhost:{PORT}",
            f"http://host.docker.internal:{PORT}",
        ],
        "routes": {
            "GET /": "same guide as GET /help",
            "GET /help": "this guide",
            "GET /health": "health and diagnostics",
            "GET /jobs": "list recent background Codex jobs",
            "GET /jobs/{job_id}": "poll background Codex progress and final output",
            "GET /winbridge/jobs": "list recent background WinBridge jobs",
            "GET /winbridge/jobs/{job_id}": "poll background WinBridge status and output",
            "GET /service-jobs": "list recent async compose service jobs",
            "GET /service-jobs/{job_id}": "poll async compose service job status",
            "GET /services": "discover all docker-compose services (dynamic from compose file)",
            "GET /services/{service}": "service details by compose service name or container_name",
            "GET /openapi.json": "OpenAPI document",
            "POST /winbridge/run": "run an allowed Windows PowerShell script directly on the host",
            "POST /winbridge/run-async": "start an allowed Windows PowerShell script directly on the host",
            "POST /run": "run codex exec on an allowed local repository",
            "POST /run-async": "start codex exec and return a job_id immediately",
            "POST /services/{service}/recreate": "clean recreate a compose service asynchronously",
            "POST /services/{service}/start": "start a compose service container",
            "POST /services/{service}/stop": "stop a compose service container",
            "POST /services/{service}/restart": "restart a compose service container",
            "POST /services/recreate": "clean recreate a compose service from JSON body asynchronously",
            "POST /services/start": "start a compose service from JSON body",
            "POST /services/stop": "stop a compose service from JSON body",
            "POST /services/restart": "restart a compose service from JSON body",
        },
        "compose": {
            "compose_file": str(COMPOSE_FILE),
            "compose_file_exists": COMPOSE_FILE.exists(),
            "docker_cmd": DOCKER_CMD,
            "include_all_profiles": COMPOSE_INCLUDE_ALL_PROFILES,
            "profile": COMPOSE_PROFILE if COMPOSE_INCLUDE_ALL_PROFILES else None,
            "timeout_seconds": COMPOSE_CMD_TIMEOUT,
            "recreate_defaults": {
                "wait_timeout": SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT,
                "poll_seconds": SERVICE_RECREATE_DEFAULT_POLL_SECONDS,
                "telegram_configured": bool(
                    FORWARDER_TELEGRAM_BOT_TOKEN and FORWARDER_TELEGRAM_CHAT_ID
                ),
            },
        },
        "winbridge": {
            "default_timeout": WINBRIDGE_DEFAULT_TIMEOUT,
            "allowed_shells": sorted(WINBRIDGE_ALLOWED_SHELLS),
            "allowed_script_roots": [str(x) for x in WINBRIDGE_ALLOWED_SCRIPT_ROOTS],
        },
        "run_json_fields": {
            "prompt": "required string; task for Codex",
            "repo": f"optional alias; one of {sorted(REPO_ALIASES.keys())}",
            "cwd": "optional path under an allowed root; use this when no repo alias fits",
            "model": f"optional string; default {DEFAULT_MODEL}",
            "approval": f"optional string; default {DEFAULT_APPROVAL}",
            "sandbox": f"optional string; default {DEFAULT_SANDBOX}",
            "timeout": f"optional integer seconds; default {DEFAULT_TIMEOUT}",
            "add_dirs": "optional list of extra allowed directories",
            "skip_git_repo_check": (
                "optional boolean; default "
                f"{DEFAULT_SKIP_GIT_REPO_CHECK}"
            ),
            "keep_alive": (
                "optional boolean for POST /run; default "
                f"{DEFAULT_RUN_KEEPALIVE}; sends JSON-safe whitespace until final result"
            ),
            "keep_alive_seconds": (
                "optional number for POST /run heartbeat interval; default "
                f"{DEFAULT_RUN_KEEPALIVE_SECONDS}"
            ),
        },
        "repo_aliases": {k: str(v) for k, v in REPO_ALIASES.items()},
        "allowed_roots": [str(x) for x in ALLOWED_ROOTS],
        "examples": {
            "help": f"curl http://127.0.0.1:{PORT}/help",
            "health": f"curl http://127.0.0.1:{PORT}/health",
            "openapi": f"curl http://127.0.0.1:{PORT}/openapi.json",
            "jobs": f"curl http://127.0.0.1:{PORT}/jobs",
            "winbridge_jobs": f"curl http://127.0.0.1:{PORT}/winbridge/jobs",
            "service_jobs": f"curl http://127.0.0.1:{PORT}/service-jobs",
            "services": f"curl http://127.0.0.1:{PORT}/services",
            "service_details": f"curl http://127.0.0.1:{PORT}/services/hermes",
            "winbridge_restart_script": (
                f"curl -X POST http://127.0.0.1:{PORT}/winbridge/run-async "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"script\\\":\\\"D:/mkt/python/hermes/workspace/scripts/docker-restart.ps1\\\","
                "\\\"cwd\\\":\\\"D:/mkt/python/hermes\\\",\\\"timeout\\\":300}\""
            ),
            "recreate_service": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/hermes/recreate "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"wait_for_url\\\":\\\"http://127.0.0.1:8642/health\\\","
                "\\\"notify\\\":{\\\"telegram\\\":true}}\""
            ),
            "start_service": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/hermes/start"
            ),
            "stop_service": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/hermes/stop"
            ),
            "restart_service": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/hermes/restart"
            ),
            "start_service_with_json": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/start "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"service\\\":\\\"hermes\\\"}\""
            ),
            "stop_service_with_json": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/stop "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"service\\\":\\\"hermes\\\"}\""
            ),
            "restart_service_with_json": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/restart "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"service\\\":\\\"hermes\\\"}\""
            ),
            "recreate_service_with_json": (
                f"curl -X POST http://127.0.0.1:{PORT}/services/recreate "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"service\\\":\\\"hermes\\\",\\\"notify\\\":{\\\"telegram\\\":true}}\""
            ),
            "run_with_repo_alias": (
                f"curl -X POST http://127.0.0.1:{PORT}/run "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"repo\\\":\\\"fish_doc_extractor\\\","
                "\\\"prompt\\\":\\\"Summarize this repository.\\\"}\""
            ),
            "run_async_with_repo_alias": (
                f"curl -X POST http://127.0.0.1:{PORT}/run-async "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"repo\\\":\\\"fish_doc_extractor\\\","
                "\\\"prompt\\\":\\\"Summarize this repository.\\\"}\""
            ),
            "poll_async_job": f"curl http://127.0.0.1:{PORT}/jobs/job_REPLACE_ME",
            "run_with_cwd": (
                f"curl -X POST http://127.0.0.1:{PORT}/run "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"cwd\\\":\\\"D:\\\\\\\\mkt\\\\\\\\python\\\\\\\\Fish_Doc_Extractor\\\","
                "\\\"prompt\\\":\\\"Summarize this repository.\\\"}\""
            ),
        },
        "common_mistakes": [
            "Use POST /run for tasks; GET /run only returns this guide.",
            "Use POST /run-async for long tasks so callers can poll progress instead of waiting on one HTTP request.",
            "Use POST /winbridge/run-async for host PowerShell scripts; this bypasses codex exec sandboxing but still inherits the Windows account permissions of the forwarder process.",
            "Use POST /services/{service}/recreate for self-restarts so the host can keep working while the target container restarts.",
            "POST /run sends whitespace keepalives before the final JSON; JSON parsers should ignore this leading whitespace.",
            "Send a JSON body with Content-Type: application/json.",
            "Include either repo or cwd when calling POST /run.",
            "Do not send command/args; this service delegates natural-language prompts to Codex CLI.",
            "Service names come from docker compose config and can change when the compose file changes.",
            "If compose service discovery fails, check docker daemon state and the compose file path in /health.",
            "Treat stage=empty_output as no usable answer, even though the Codex process exited 0.",
            "Keep cwd and add_dirs under the allowed roots listed above.",
            "Use /health first when checking whether the forwarder is reachable.",
        ],
    }

    if requested_path or method or error:
        payload["request"] = {
            "method": method,
            "path": requested_path,
            "error": error,
        }
        if original_status is not None:
            payload["request"]["original_status"] = original_status

    return payload


def build_openapi() -> dict[str, Any]:
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Codex Forwarder",
            "version": "1.6.0",
            "description": (
                "HTTP wrapper around Codex CLI with Docker Compose service discovery "
                "and restart endpoints."
            ),
        },
        "paths": {
            "/": {
                "get": {
                    "summary": "Help guide",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/help": {
                "get": {
                    "summary": "Human and agent-readable usage guide",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/health": {
                "get": {
                    "summary": "Health and diagnostics",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/jobs": {
                "get": {
                    "summary": "List recent background Codex jobs",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/jobs/{job_id}": {
                "get": {
                    "summary": "Poll background Codex progress and final output",
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Job status"},
                        "404": {"description": "Job not found or expired"},
                    },
                }
            },
            "/winbridge/jobs": {
                "get": {
                    "summary": "List recent background WinBridge jobs",
                    "responses": {"200": {"description": "WinBridge job list"}},
                }
            },
            "/winbridge/jobs/{job_id}": {
                "get": {
                    "summary": "Poll background WinBridge progress and final output",
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "WinBridge job status"},
                        "404": {"description": "WinBridge job not found"},
                    },
                }
            },
            "/service-jobs": {
                "get": {
                    "summary": "List recent async compose service jobs",
                    "responses": {"200": {"description": "Service job list"}},
                }
            },
            "/service-jobs/{job_id}": {
                "get": {
                    "summary": "Poll async compose service job progress and final status",
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Service job status"},
                        "404": {"description": "Service job not found"},
                    },
                }
            },
            "/services": {
                "get": {
                    "summary": "List compose services discovered from docker-compose.yml",
                    "responses": {"200": {"description": "Service list"}},
                }
            },
            "/services/{service}": {
                "get": {
                    "summary": "Get one compose service by service name or container name",
                    "parameters": [
                        {
                            "name": "service",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Service details"},
                        "404": {"description": "Service not found"},
                    },
                }
            },
            "/services/{service}/restart": {
                "post": {
                    "summary": "Restart one compose service container",
                    "parameters": [
                        {
                            "name": "service",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Restart result"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Restart failed"},
                    },
                }
            },
            "/services/{service}/start": {
                "post": {
                    "summary": "Start one compose service container",
                    "parameters": [
                        {
                            "name": "service",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Start result"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Start failed"},
                    },
                }
            },
            "/services/{service}/stop": {
                "post": {
                    "summary": "Stop one compose service container",
                    "parameters": [
                        {
                            "name": "service",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Stop result"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Stop failed"},
                    },
                }
            },
            "/services/{service}/recreate": {
                "post": {
                    "summary": "Clean recreate one compose service asynchronously",
                    "parameters": [
                        {
                            "name": "service",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "clean": {"type": "boolean", "default": True},
                                        "no_deps": {"type": "boolean", "default": True},
                                        "wait_for_url": {"type": "string"},
                                        "wait_timeout": {"type": "integer", "default": SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT},
                                        "poll_seconds": {"type": "number", "default": SERVICE_RECREATE_DEFAULT_POLL_SECONDS},
                                        "notify": {
                                            "type": "object",
                                            "properties": {
                                                "telegram": {"type": "boolean"},
                                                "message": {"type": "string"},
                                                "webhook_url": {"type": "string"},
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Accepted service recreate job"},
                        "400": {"description": "Bad request"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Recreate failed"},
                    },
                }
            },
            "/services/start": {
                "post": {
                    "summary": "Start one compose service by JSON body {\"service\": \"name\"}",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "service": {"type": "string"},
                                    },
                                    "required": ["service"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Start result"},
                        "400": {"description": "Bad request"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Start failed"},
                    },
                }
            },
            "/services/stop": {
                "post": {
                    "summary": "Stop one compose service by JSON body {\"service\": \"name\"}",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "service": {"type": "string"},
                                    },
                                    "required": ["service"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Stop result"},
                        "400": {"description": "Bad request"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Stop failed"},
                    },
                }
            },
            "/services/restart": {
                "post": {
                    "summary": "Restart one compose service by JSON body {\"service\": \"name\"}",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "service": {"type": "string"},
                                    },
                                    "required": ["service"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Restart result"},
                        "400": {"description": "Bad request"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Restart failed"},
                    },
                }
            },
            "/services/recreate": {
                "post": {
                    "summary": "Clean recreate one compose service by JSON body",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "service": {"type": "string"},
                                        "clean": {"type": "boolean", "default": True},
                                        "no_deps": {"type": "boolean", "default": True},
                                        "wait_for_url": {"type": "string"},
                                        "wait_timeout": {"type": "integer", "default": SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT},
                                        "poll_seconds": {"type": "number", "default": SERVICE_RECREATE_DEFAULT_POLL_SECONDS},
                                        "notify": {
                                            "type": "object",
                                            "properties": {
                                                "telegram": {"type": "boolean"},
                                                "message": {"type": "string"},
                                                "webhook_url": {"type": "string"},
                                            },
                                        },
                                    },
                                    "required": ["service"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Accepted service recreate job"},
                        "400": {"description": "Bad request"},
                        "404": {"description": "Service not found"},
                        "500": {"description": "Recreate failed"},
                    },
                }
            },
            "/openapi.json": {
                "get": {
                    "summary": "OpenAPI schema",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/winbridge/run": {
                "post": {
                    "summary": "Run an allowed Windows PowerShell script directly on the host",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "shell": {
                                            "type": "string",
                                            "default": "powershell",
                                        },
                                        "script": {"type": "string"},
                                        "cwd": {"type": "string"},
                                        "args": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "timeout": {
                                            "type": "integer",
                                            "default": WINBRIDGE_DEFAULT_TIMEOUT,
                                        },
                                    },
                                    "required": ["script"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "WinBridge execution result"},
                        "400": {"description": "Bad request"},
                        "408": {"description": "Timeout"},
                        "500": {"description": "Internal error"},
                    },
                }
            },
            "/winbridge/run-async": {
                "post": {
                    "summary": "Start an allowed Windows PowerShell script directly on the host and return a job id",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "shell": {
                                            "type": "string",
                                            "default": "powershell",
                                        },
                                        "script": {"type": "string"},
                                        "cwd": {"type": "string"},
                                        "args": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "timeout": {
                                            "type": "integer",
                                            "default": WINBRIDGE_DEFAULT_TIMEOUT,
                                        },
                                    },
                                    "required": ["script"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Started WinBridge job status"},
                        "400": {"description": "Bad request"},
                        "500": {"description": "Internal error"},
                    },
                }
            },
            "/run": {
                "post": {
                    "summary": "Run Codex on an approved local repository",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "Optional repo alias",
                                        },
                                        "cwd": {
                                            "type": "string",
                                            "description": "Optional raw Windows path",
                                        },
                                        "prompt": {"type": "string"},
                                        "model": {"type": "string", "default": DEFAULT_MODEL},
                                        "approval": {
                                            "type": "string",
                                            "default": DEFAULT_APPROVAL,
                                        },
                                        "sandbox": {
                                            "type": "string",
                                            "default": DEFAULT_SANDBOX,
                                        },
                                        "timeout": {
                                            "type": "integer",
                                            "default": DEFAULT_TIMEOUT,
                                        },
                                        "add_dirs": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "skip_git_repo_check": {
                                            "type": "boolean",
                                            "default": DEFAULT_SKIP_GIT_REPO_CHECK,
                                        },
                                        "keep_alive": {
                                            "type": "boolean",
                                            "default": DEFAULT_RUN_KEEPALIVE,
                                            "description": "For POST /run, keep the HTTP response alive with JSON whitespace until final JSON is written.",
                                        },
                                        "keep_alive_seconds": {
                                            "type": "number",
                                            "default": DEFAULT_RUN_KEEPALIVE_SECONDS,
                                            "description": "Heartbeat interval for POST /run keepalive whitespace.",
                                        },
                                    },
                                    "required": ["prompt"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Codex execution result"},
                        "400": {"description": "Bad request"},
                        "408": {"description": "Timeout"},
                        "500": {"description": "Internal error"},
                    },
                }
            },
            "/run-async": {
                "post": {
                    "summary": "Start Codex on an approved local repository and return a job id",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "Optional repo alias",
                                        },
                                        "cwd": {
                                            "type": "string",
                                            "description": "Optional raw Windows path",
                                        },
                                        "prompt": {"type": "string"},
                                        "model": {"type": "string", "default": DEFAULT_MODEL},
                                        "approval": {
                                            "type": "string",
                                            "default": DEFAULT_APPROVAL,
                                        },
                                        "sandbox": {
                                            "type": "string",
                                            "default": DEFAULT_SANDBOX,
                                        },
                                        "timeout": {
                                            "type": "integer",
                                            "default": DEFAULT_TIMEOUT,
                                        },
                                        "add_dirs": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "skip_git_repo_check": {
                                            "type": "boolean",
                                            "default": DEFAULT_SKIP_GIT_REPO_CHECK,
                                        },
                                        "keep_alive": {
                                            "type": "boolean",
                                            "default": DEFAULT_RUN_KEEPALIVE,
                                        },
                                        "keep_alive_seconds": {
                                            "type": "number",
                                            "default": DEFAULT_RUN_KEEPALIVE_SECONDS,
                                        },
                                    },
                                    "required": ["prompt"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Started job status"},
                        "400": {"description": "Bad request"},
                        "500": {"description": "Internal error"},
                    },
                }
            },
        },
    }
