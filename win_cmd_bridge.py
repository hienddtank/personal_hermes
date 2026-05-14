"""Windows Command Bridge — HTTP server to execute arbitrary commands on the host.

Usage: python win_cmd_bridge.py [port] [--host 0.0.0.0]
Default port: 9999

From inside the container:
    curl -X POST http://host.docker.internal:9999/exec \
      -H "Content-Type: application/json" \
      -d '{"cmd": "dir /b", "shell": "powershell"}'
"""

import json
import subprocess
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ─── Config ────────────────────────────────────────────────────────────────
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB cap per command
ALLOWED_SHELLS = {"powershell", "cmd", "pwsh"}

# ─── Command Execution ─────────────────────────────────────────────────────
def run_command(cmd: str, shell: str = "powershell") -> dict:
    """Execute a command on the Windows host."""
    if shell not in ALLOWED_SHELLS:
        return {"error": f"Unsupported shell: {shell}. Allowed: {sorted(ALLOWED_SHELLS)}"}

    if shell == "powershell":
        exe = "powershell.exe"
    elif shell == "pwsh":
        exe = "pwsh.exe"
    else:
        exe = "cmd.exe"

    try:
        proc = subprocess.run(
            [exe, "/c", cmd],
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout per command
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {
            "error": "Command timed out after 300 seconds",
            "exit_code": -1,
        }
    except FileNotFoundError as e:
        return {
            "error": f"Shell not found: {exe}. Make sure it's in PATH.",
            "exit_code": -1,
        }

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    # Truncate if too large
    stdout_trunc = 0
    stderr_trunc = 0
    if len(stdout) > MAX_OUTPUT_BYTES:
        stdout_trunc = len(stdout) - MAX_OUTPUT_BYTES
        stdout = stdout[-MAX_OUTPUT_BYTES:]
    if len(stderr) > MAX_OUTPUT_BYTES:
        stderr_trunc = len(stderr) - MAX_OUTPUT_BYTES
        stderr = stderr[-MAX_OUTPUT_BYTES:]

    return {
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "shell": shell,
        "cmd": cmd,
        "stdout_truncated_chars": stdout_trunc,
        "stderr_truncated_chars": stderr_trunc,
    }


# ─── HTTP Handler ──────────────────────────────────────────────────────────
class BridgeHandler(BaseHTTPRequestHandler):
    """Handle /exec and /health endpoints."""

    def _send_json(self, data: dict, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    # ─── POST routes ──────────────────────────────────────────────────────
    def do_POST(self):
        raw = self._read_body()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return self._send_json({"error": f"Invalid JSON: {e}"}, 400)

        if self.path == "/exec":
            cmd = data.get("cmd", "")
            shell = data.get("shell", "powershell")
            if not cmd:
                return self._send_json({"error": "Missing 'cmd' field"}, 400)
            result = run_command(cmd, shell)
            return self._send_json(result)

        elif self.path == "/health":
            return self._send_json({
                "ok": True,
                "shells": sorted(ALLOWED_SHELLS),
                "max_output_bytes": MAX_OUTPUT_BYTES,
                "uptime": "running",
            })

        else:
            return self._send_json({
                "error": f"Unknown route: {self.path}",
                "routes": ["/exec", "/health"],
            }, 404)

    # ─── GET routes ───────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/health":
            return self._send_json({
                "ok": True,
                "shells": sorted(ALLOWED_SHELLS),
                "max_output_bytes": MAX_OUTPUT_BYTES,
                "usage": "POST /exec with {cmd, shell}",
            })
        return self._send_json({"ok": True, "health": "/health", "exec": "POST /exec"}, 200)

    # ─── Suppress default logging ─────────────────────────────────────────
    def log_message(self, format, *args):
        pass  # Silence logs (noisy in production)


# ─── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), BridgeHandler)
    print(f"Windows Command Bridge running on http://{LISTEN_HOST}:{LISTEN_PORT}")
    print(f"  Shells: {sorted(ALLOWED_SHELLS)}")
    print(f"  Max output: {MAX_OUTPUT_BYTES // 1024} KB")
    print(f"  From container: curl -X POST http://host.docker.internal:{LISTEN_PORT}/exec ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
