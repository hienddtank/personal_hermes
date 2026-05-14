"""Run Windows .exe files via Wine inside the container.

Usage:
    python run_win_exe_wine.py "C:\\tools\\link_to_tools\\AnyDesk.exe" --args "--version"
    python run_win_exe_wine.py "F:\\miniconda\\codex.cmd"
    python run_win_exe_wine.py --path "/host/d/tools/AnyDesk.exe" --args "--safe-mode"

GUI apps launch in virtual display (:99) — use --screenshot to capture output.
"""

import json
import os
import subprocess
import sys

WINE = "wine"
DISPLAY = ":99"
TOOLS_LINK = "C:\\tools\\link_to_tools"


def wine_run(args: list[str], timeout=30, env=None) -> dict:
    """Run a command via Wine."""
    full_env = os.environ.copy()
    full_env["DISPLAY"] = DISPLAY
    if env:
        full_env.update(env)

    try:
        proc = subprocess.run(
            [WINE] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=full_env,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Timed out after {timeout}s", "exit_code": -1}

    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def run_exe(exe_path: str, args: str = "", timeout: int = 30) -> dict:
    """Run a Windows .exe via Wine."""
    cmd_args = [exe_path]
    if args.strip():
        # Quote args properly for Wine
        cmd_args += args.split()
    return wine_run(cmd_args, timeout=timeout)


def path_to_wine_path(path: str) -> str:
    """Convert a Linux path to a Wine DOS path."""
    # If it's in /host/d/tools/, convert to C:\tools\link_to_tools\...
    if path.startswith("/host/d/tools/"):
        return "C:\\tools\\link_to_tools\\" + path[len("/host/d/tools/"):]
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(__doc__)
        sys.exit(0)

    exe = None
    args_str = ""
    timeout = 30

    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == "--path":
            i += 1
            exe = path_to_wine_path(sys.argv[i])
        elif sys.argv[i] == "--args":
            i += 1
            args_str = " ".join(sys.argv[i:])
            break
        elif sys.argv[i] == "--timeout":
            i += 1
            timeout = int(sys.argv[i])
        elif not exe:
            exe = path_to_wine_path(sys.argv[i])
        i += 1

    if not exe:
        print("Error: No .exe path provided")
        sys.exit(1)

    print(f"Running: {exe}")
    if args_str:
        print(f"Args:    {args_str}")
    print()

    result = run_exe(exe, args_str, timeout=timeout)

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
