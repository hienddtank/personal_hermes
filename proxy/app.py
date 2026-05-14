import logging
import os
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proxy.chat_completions import router as chat_completions_router
    from proxy.core import DEFAULT_HOST, DEFAULT_PORT, LMStudioProxy
    from proxy.health import router as health_router
    from proxy.metrics import router as metrics_router
    from proxy.passthrough import router as passthrough_router
else:
    from .chat_completions import router as chat_completions_router
    from .core import DEFAULT_HOST, DEFAULT_PORT, LMStudioProxy
    from .health import router as health_router
    from .metrics import router as metrics_router
    from .passthrough import router as passthrough_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        proxy = getattr(app.state, "proxy", None)
        if proxy is not None:
            await proxy.close()


def create_app(proxy: Optional[LMStudioProxy] = None) -> FastAPI:
    app = FastAPI(
        title="Hermes LM Studio Proxy",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.proxy = proxy or LMStudioProxy()
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(chat_completions_router)
    # Register last so explicit local endpoints win and everything else relays upstream.
    app.include_router(passthrough_router)
    return app


app = create_app()


def port_cleaner_enabled() -> bool:
    return os.getenv("PROXY_CLEAN_PORT_ON_START", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def pids_on_tcp_port(port: int) -> set[int]:
    if os.name == "nt":
        return windows_pids_on_tcp_port(port)
    return unix_pids_on_tcp_port(port)


def windows_pids_on_tcp_port(port: int) -> set[int]:
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=create_no_window,
            check=False,
        )
    except Exception:
        logging.exception("Failed to inspect Windows TCP ports")
        return set()

    pids: set[int] = set()
    port_suffix = f":{port}"
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        if not local_address.endswith(port_suffix):
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return pids


def unix_pids_on_tcp_port(port: int) -> set[int]:
    commands = (
        ["lsof", "-ti", f"tcp:{port}"],
        ["fuser", f"{port}/tcp"],
    )
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except FileNotFoundError:
            continue
        except Exception:
            logging.exception("Failed to inspect TCP port with %s", command[0])
            continue

        output = " ".join(part for part in (result.stdout, result.stderr) if part)
        pids = {int(token) for token in output.split() if token.isdigit()}
        if pids:
            return pids
    return set()


def kill_pids(pids: set[int], port: int) -> None:
    current_pid = os.getpid()
    targets = sorted(pid for pid in pids if pid != current_pid)
    if not targets:
        return

    logging.warning("Killing processes occupying proxy port %s: %s", port, targets)
    for pid in targets:
        try:
            if os.name == "nt":
                create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=create_no_window,
                    check=False,
                )
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except Exception:
            logging.exception("Failed to kill process %s on proxy port", pid)


def clean_proxy_port(port: int) -> None:
    if not port_cleaner_enabled():
        return

    wait_seconds = float(os.getenv("PROXY_CLEAN_PORT_WAIT_SECONDS", "5"))
    deadline = time.monotonic() + max(wait_seconds, 0)

    while True:
        pids = pids_on_tcp_port(port)
        kill_pids(pids, port)
        remaining = {pid for pid in pids_on_tcp_port(port) if pid != os.getpid()}
        if not remaining:
            return
        if time.monotonic() >= deadline:
            logging.warning(
                "Proxy port %s is still occupied after cleanup attempt: %s",
                port,
                sorted(remaining),
            )
            return
        time.sleep(0.25)


def main() -> None:
    import uvicorn

    logging.basicConfig(
        level=os.getenv("PROXY_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    clean_proxy_port(DEFAULT_PORT)
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    main()
