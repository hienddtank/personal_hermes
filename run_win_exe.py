"""Run Windows .exe apps from the container via the HTTP bridge.

Usage:
    python run_win_exe.py "D:\\tools\\AnyDesk.exe"
    python run_win_exe.py "C:\\Program Files\\Adobe\\Adobe Photoshop 2020\\Photoshop.exe" --args "--safe-mode"
    python run_win_exe.py "F:\\miniconda\\codex.cmd"

From container CLI (alternative):
    curl -X POST http://host.docker.internal:9999/exec \
      -d '{"cmd": "\"D:\\\\tools\\\\AnyDesk.exe\"", "shell": "powershell"}'
"""

import json
import sys
import urllib.request

HOST = "host.docker.internal"
PORT = 9999


def run_exe(exe_path: str, args: str = "", shell: str = "powershell") -> dict:
    """Launch a Windows executable from the container."""
    # Build command to launch the .exe
    if args.strip():
        cmd = f'& "{exe_path}" {args}'
    else:
        cmd = f'& "{exe_path}"'

    payload = json.dumps({"cmd": cmd, "shell": shell}).encode("utf-8")
    url = f"http://{HOST}:{PORT}/exec"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=305) as resp:
        return json.loads(resp.read().decode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_win_exe.py '<path_to_exe>' [--args 'additional args']")
        print()
        print("Examples:")
        print('  python run_win_exe.py "D:\\tools\\AnyDesk.exe"')
        print('  python run_win_exe.py "C:\\Program Files\\Adobe\\Illustrator 2020\\Illustrator.exe" --args "--safe-mode"')
        print('  python run_win_exe.py "F:\\miniconda\\codex.cmd"')
        sys.exit(1)

    exe = sys.argv[1]
    extra_args = ""
    for i, arg in enumerate(sys.argv):
        if arg == "--args" and i + 1 < len(sys.argv):
            extra_args = " ".join(sys.argv[i + 2:])
            break

    print(f"Launching: {exe}")
    if extra_args:
        print(f"Args:     {extra_args}")
    print()

    result = run_exe(exe, extra_args)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(result.get("exit_code", 1))

    print(f"Exit code: {result.get('exit_code', 'N/A')}")
    if result.get("stdout"):
        print(f"\n--- STDOUT ({len(result['stdout'])} chars) ---")
        print(result["stdout"])
    if result.get("stderr"):
        print(f"\n--- STDERR ({len(result['stderr'])} chars) ---")
        print(result["stderr"])
