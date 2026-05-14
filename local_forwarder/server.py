from __future__ import annotations

import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from local_forwarder.config import (
        ALLOWED_ROOTS,
        CODEX_CMD,
        COMPOSE_FILE,
        COMPOSE_INCLUDE_ALL_PROFILES,
        COMPOSE_PROFILE,
        DOCKER_CMD,
        HOST,
        PORT,
        REPO_ALIASES,
        WINBRIDGE_ALLOWED_SCRIPT_ROOTS,
        WINBRIDGE_DEFAULT_TIMEOUT,
    )
    from local_forwarder.handler import Handler
    from local_forwarder.request_logging import prune_old_request_logs, request_log_config
    from local_forwarder.utils import now_iso
else:
    from .config import (
        ALLOWED_ROOTS,
        CODEX_CMD,
        COMPOSE_FILE,
        COMPOSE_INCLUDE_ALL_PROFILES,
        COMPOSE_PROFILE,
        DOCKER_CMD,
        HOST,
        PORT,
        REPO_ALIASES,
        WINBRIDGE_ALLOWED_SCRIPT_ROOTS,
        WINBRIDGE_DEFAULT_TIMEOUT,
    )
    from .handler import Handler
    from .request_logging import prune_old_request_logs, request_log_config
    from .utils import now_iso


def main() -> None:
    prune_result = prune_old_request_logs(force=True)
    print(f"[{now_iso()}] Starting Codex forwarder on http://{HOST}:{PORT}")
    print(f"[{now_iso()}] CODEX_CMD = {CODEX_CMD}")
    print(
        f"[{now_iso()}] COMPOSE = "
        f"{{'file': '{COMPOSE_FILE}', 'docker_cmd': '{DOCKER_CMD}', "
        f"'include_all_profiles': {COMPOSE_INCLUDE_ALL_PROFILES}, "
        f"'profile': '{COMPOSE_PROFILE if COMPOSE_INCLUDE_ALL_PROFILES else ''}'}}"
    )
    print(f"[{now_iso()}] ALLOWED_ROOTS = {[str(x) for x in ALLOWED_ROOTS]}")
    print(f"[{now_iso()}] REPO_ALIASES = { {k: str(v) for k, v in REPO_ALIASES.items()} }")
    print(
        f"[{now_iso()}] WINBRIDGE = "
        f"{{'timeout': {WINBRIDGE_DEFAULT_TIMEOUT}, "
        f"'script_roots': {[str(x) for x in WINBRIDGE_ALLOWED_SCRIPT_ROOTS]}}}"
    )
    print(f"[{now_iso()}] REQUEST_LOGS = {request_log_config()}")
    print(f"[{now_iso()}] REQUEST_LOG_PRUNE = {prune_result}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
