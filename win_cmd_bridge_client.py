"""Container-side helper to call the Windows Command Bridge.

Usage:
    python win_cmd_bridge_client.py "dir /b" --shell powershell
    python win_cmd_bridge_client.py "Get-Process | Select Name,CPU" --shell powershell
    python win_cmd_bridge_client.py "ipconfig" --shell cmd
"""

import json
import sys
import urllib.request

HOST = "host.docker.internal"
PORT = 9999


def run(cmd: str, shell: str = "powershell") -> dict:
    payload = json.dumps({"cmd": cmd, "shell": shell}).encode("utf-8")
    url = f"http://{HOST}:{PORT}/exec"
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=305) as resp:
        return json.loads(resp.read().decode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python win_cmd_bridge_client.py '<command>' [--shell powershell|cmd]")
        sys.exit(1)

    cmd = sys.argv[1]
    shell = "powershell"
    for i, arg in enumerate(sys.argv):
        if arg == "--shell" and i + 1 < len(sys.argv):
            shell = sys.argv[i + 1]

    print(f"Running: {cmd} (shell: {shell})")
    result = run(cmd, shell)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(result.get("exit_code", 1))

    print(f"\n--- STDOUT ({len(result['stdout'])} chars) ---")
    print(result["stdout"])
    if result.get("stderr"):
        print(f"\n--- STDERR ({len(result['stderr'])} chars) ---")
        print(result["stderr"])
    if result.get("stdout_truncated_chars"):
        print(f"\n[TRUNCATED: {result['stdout_truncated_chars']} chars dropped from start]")
