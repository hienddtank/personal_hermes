from __future__ import annotations

import os
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8768


def host_mount_path(path: str | Path) -> Path:
    raw = str(path).replace("\\", "/")
    parts = [part for part in raw.split("/") if part]
    if os.name == "nt" and len(parts) >= 2 and parts[0].lower() == "host" and len(parts[1]) == 1:
        drive = parts[1].upper()
        rest = "/".join(parts[2:])
        return Path(f"{drive}:/{rest}").resolve()
    return Path(str(path)).resolve()

def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def read_dotenv_value(project_root: Path, name: str) -> str:
    env_path = project_root / ".env"
    if not env_path.exists():
        return ""
    prefix = f"{name}="
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or not line.startswith(prefix):
                continue
            return line[len(prefix) :].strip().strip("\"'")
    except Exception:
        return ""
    return ""

# Exact Windows launcher path.
CODEX_CMD = r"F:\miniconda\codex.cmd"

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# Keep this as tight as possible.
ALLOWED_ROOTS = [
    host_mount_path("/host/d/mkt/python"),
]

# Optional aliases so the agent does not have to remember raw paths.
REPO_ALIASES = {
    "fish_doc_extractor": host_mount_path("/host/d/mkt/python/Fish_Doc_Extractor"),
    "fish_store_front": host_mount_path("/host/d/mkt/python/Fish_Store_Front"),
    "hermes_workspace": host_mount_path("/host/d/mkt/python/hermes/workspace"),
}

DEFAULT_MODEL = "gpt-5.4"
DEFAULT_APPROVAL = "never"
DEFAULT_SANDBOX = "workspace-write"
DEFAULT_TIMEOUT = 1800
DEFAULT_SKIP_GIT_REPO_CHECK = True
DEFAULT_RUN_KEEPALIVE = os.getenv("FORWARDER_RUN_KEEPALIVE", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_RUN_KEEPALIVE_SECONDS = max(
    1.0,
    env_float("FORWARDER_RUN_KEEPALIVE_SECONDS", 15.0),
)
WINBRIDGE_DEFAULT_TIMEOUT = int(os.getenv("FORWARDER_WINBRIDGE_TIMEOUT", "600"))
WINBRIDGE_ALLOWED_SCRIPT_ROOTS = [
    (PROJECT_ROOT / "workspace" / "scripts").resolve(),
    (PROJECT_ROOT / "workspace").resolve(),
]
WINBRIDGE_ALLOWED_SHELLS = {"powershell"}

DOCKER_CMD = os.getenv("FORWARDER_DOCKER_CMD", "docker").strip() or "docker"
COMPOSE_FILE = Path(
    os.getenv(
        "FORWARDER_COMPOSE_FILE",
        str(PROJECT_ROOT / "docker-compose.yml"),
    )
).resolve()
COMPOSE_INCLUDE_ALL_PROFILES = os.getenv(
    "FORWARDER_COMPOSE_INCLUDE_ALL_PROFILES",
    "true",
).lower() in {"1", "true", "yes", "on"}
COMPOSE_PROFILE = os.getenv("FORWARDER_COMPOSE_PROFILE", "*").strip() or "*"
COMPOSE_CMD_TIMEOUT = int(os.getenv("FORWARDER_COMPOSE_TIMEOUT", "60"))
FORWARDER_TELEGRAM_BOT_TOKEN = (
    os.getenv("FORWARDER_TELEGRAM_BOT_TOKEN", "").strip()
    or read_dotenv_value(PROJECT_ROOT, "TELEGRAM_BOT_TOKEN")
)
FORWARDER_TELEGRAM_CHAT_ID = (
    os.getenv("FORWARDER_TELEGRAM_CHAT_ID", "").strip()
    or read_dotenv_value(PROJECT_ROOT, "HERMES_TELEGRAM_CHAT_ID")
    or read_dotenv_value(PROJECT_ROOT, "TELEGRAM_CHAT_ID")
    or "6730547288"
)
SERVICE_RECREATE_DEFAULT_WAIT_TIMEOUT = int(
    os.getenv("FORWARDER_SERVICE_RECREATE_WAIT_TIMEOUT", "180")
)
SERVICE_RECREATE_DEFAULT_POLL_SECONDS = max(
    1.0,
    env_float("FORWARDER_SERVICE_RECREATE_POLL_SECONDS", 3.0),
)

# Local request payload audit log. Files older than this are pruned on startup
# and periodically while handling traffic.
LOG_DIR = PROJECT_ROOT / "logs" / "local_forwarder"
LOG_RETENTION_DAYS = 3
LOG_PRUNE_INTERVAL_SECONDS = 3600
LOG_HEADER_ALLOWLIST = {
    "accept",
    "content-length",
    "content-type",
    "host",
    "user-agent",
}

ASYNC_JOB_RETENTION_SECONDS = 6 * 60 * 60
ASYNC_OUTPUT_LIMIT_CHARS = 25 * 1024 * 1024
ASYNC_POLL_AFTER_SECONDS = 2
