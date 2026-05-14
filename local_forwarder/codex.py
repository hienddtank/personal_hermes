from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .config import (
    ALLOWED_ROOTS,
    CODEX_CMD,
    DEFAULT_APPROVAL,
    DEFAULT_MODEL,
    DEFAULT_RUN_KEEPALIVE,
    DEFAULT_RUN_KEEPALIVE_SECONDS,
    DEFAULT_SANDBOX,
    DEFAULT_SKIP_GIT_REPO_CHECK,
    DEFAULT_TIMEOUT,
    REPO_ALIASES,
    host_mount_path,
)
from .utils import bool_from_value, now_iso, path_info


def resolve_repo_or_cwd(data: dict[str, Any]) -> Path:
    """
    Accept either:
      - {"repo": "fish_doc_extractor"}
      - {"cwd": "D:\\mkt\\python\\Fish_Doc_Extractor"}
    """
    repo = data.get("repo")
    cwd = data.get("cwd")

    if repo:
        repo_key = str(repo).strip().lower()
        if repo_key not in REPO_ALIASES:
            raise ValueError(
                f"Unknown repo alias: {repo_key}. "
                f"Known aliases: {sorted(REPO_ALIASES.keys())}"
            )
        target = REPO_ALIASES[repo_key]
        return ensure_allowed_path(target)

    if cwd:
        return ensure_allowed_path(str(cwd))

    raise ValueError("Either 'repo' or 'cwd' must be provided.")


def ensure_allowed_path(p: Path | str) -> Path:
    p = host_mount_path(p)

    if not p.exists():
        raise ValueError(f"Path does not exist: {p}")

    for root in ALLOWED_ROOTS:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue

    raise ValueError(
        f"Path not allowed: {p}. "
        f"Allowed roots: {[str(x) for x in ALLOWED_ROOTS]}"
    )


def normalize_add_dirs(add_dirs_raw: Any) -> list[Path]:
    if add_dirs_raw is None:
        return []
    if not isinstance(add_dirs_raw, list):
        raise ValueError("Field 'add_dirs' must be a list.")
    out: list[Path] = []
    for item in add_dirs_raw:
        out.append(ensure_allowed_path(str(item)))
    return out


def parse_run_payload(data: dict[str, Any]) -> dict[str, Any]:
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("Field 'prompt' is required and cannot be empty.")

    cwd = resolve_repo_or_cwd(data)
    model = str(data.get("model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL
    approval = str(data.get("approval", DEFAULT_APPROVAL)).strip() or DEFAULT_APPROVAL
    sandbox = str(data.get("sandbox", DEFAULT_SANDBOX)).strip() or DEFAULT_SANDBOX
    timeout = int(data.get("timeout", DEFAULT_TIMEOUT))
    if timeout <= 0:
        raise ValueError("Field 'timeout' must be a positive integer.")
    add_dirs = normalize_add_dirs(data.get("add_dirs"))
    skip_git_repo_check = bool_from_value(
        data.get("skip_git_repo_check"),
        DEFAULT_SKIP_GIT_REPO_CHECK,
    )
    keep_alive = bool_from_value(data.get("keep_alive"), DEFAULT_RUN_KEEPALIVE)
    keep_alive_seconds = float(
        data.get("keep_alive_seconds", DEFAULT_RUN_KEEPALIVE_SECONDS)
    )
    if keep_alive_seconds <= 0:
        raise ValueError("Field 'keep_alive_seconds' must be positive.")

    config: dict[str, Any] = {
        "prompt": prompt,
        "cwd": cwd,
        "model": model,
        "approval": approval,
        "sandbox": sandbox,
        "timeout": timeout,
        "add_dirs": add_dirs,
        "skip_git_repo_check": skip_git_repo_check,
        "keep_alive": keep_alive,
        "keep_alive_seconds": keep_alive_seconds,
    }
    config["cmd"] = build_codex_command(config)
    return config


def build_codex_command(config: dict[str, Any]) -> list[str]:
    cmd = [
        "cmd",
        "/c",
        CODEX_CMD,
        "exec",
        "-C",
        str(config["cwd"]),
        "--model",
        config["model"],
        "-c",
        f"approval_policy={config['approval']}",
        "-c",
        f"sandbox_mode={config['sandbox']}",
    ]

    if config["skip_git_repo_check"]:
        cmd.append("--skip-git-repo-check")

    for d in config["add_dirs"]:
        cmd += ["--add-dir", str(d)]

    cmd.append(config["prompt"])
    return cmd


def run_config_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "cwd": str(config["cwd"]),
        "cwd_info": path_info(str(config["cwd"])),
        "model": config["model"],
        "approval": config["approval"],
        "sandbox": config["sandbox"],
        "timeout": config["timeout"],
        "add_dirs": [str(d) for d in config["add_dirs"]],
        "skip_git_repo_check": config["skip_git_repo_check"],
        "keep_alive": config.get("keep_alive", DEFAULT_RUN_KEEPALIVE),
        "keep_alive_seconds": config.get(
            "keep_alive_seconds",
            DEFAULT_RUN_KEEPALIVE_SECONDS,
        ),
        "cmd": config["cmd"],
    }


def validation_error_context(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "received": {
            "repo": data.get("repo"),
            "cwd": data.get("cwd"),
            "prompt_preview": str(data.get("prompt", ""))[:300],
            "model": data.get("model"),
            "approval": data.get("approval"),
            "sandbox": data.get("sandbox"),
            "timeout": data.get("timeout"),
            "add_dirs": data.get("add_dirs"),
            "skip_git_repo_check": data.get("skip_git_repo_check"),
            "keep_alive": data.get("keep_alive"),
            "keep_alive_seconds": data.get("keep_alive_seconds"),
        },
        "cwd_info": path_info(str(data.get("cwd"))) if data.get("cwd") else None,
        "allowed_roots": [str(x) for x in ALLOWED_ROOTS],
        "repo_aliases": {k: str(v) for k, v in REPO_ALIASES.items()},
    }


def output_is_empty(stdout_text: str, stderr_text: str) -> bool:
    return not stdout_text.strip() and not stderr_text.strip()


def output_state(stdout_text: str, stderr_text: str) -> str:
    has_stdout = bool(stdout_text.strip())
    has_stderr = bool(stderr_text.strip())
    if has_stdout and has_stderr:
        return "stdout_and_stderr"
    if has_stdout:
        return "stdout"
    if has_stderr:
        return "stderr"
    return "empty"


def result_stage(returncode: int | None, stdout_text: str, stderr_text: str) -> str:
    if returncode == 0 and output_is_empty(stdout_text, stderr_text):
        return "empty_output"
    if returncode == 0:
        return "completed"
    return "codex_exit_nonzero"


def empty_output_error(returncode: int | None, stdout_text: str, stderr_text: str) -> str | None:
    if returncode == 0 and output_is_empty(stdout_text, stderr_text):
        return "Codex exited successfully but produced no stdout or stderr."
    return None


def build_codex_hints(returncode_ok: bool, stderr_text: str, stdout_text: str = "") -> list[str]:
    hints: list[str] = []
    if returncode_ok and output_is_empty(stdout_text, stderr_text):
        hints.append("Codex returned no output. Treat this as no usable answer, not as successful file content.")
        hints.append("Do not retry with command/args payloads; this forwarder only accepts prompt plus repo or cwd.")
        hints.append("Check request_log.body to confirm the prompt, repo, and cwd that were sent.")
        hints.append("Ask Codex to explicitly print the result or summarize the target files, or use direct file/shell tools when raw file reads are needed.")
    if not returncode_ok:
        hints.append("Codex started but returned a non-zero exit code.")
        hints.append("Inspect stderr_preview first, then stdout_preview, then cmd.")
        stderr_lower = stderr_text.lower()
        if "approval" in stderr_lower:
            hints.append("The approval policy may be incompatible with the current task or CLI version.")
        if "sandbox" in stderr_lower:
            hints.append("The sandbox mode may need adjustment for this repository.")
        if "not found" in stderr_lower:
            hints.append("A referenced file, command, or dependency may not exist.")
        if "git" in stderr_lower:
            hints.append("The repository may not be detected as a git repo. skip_git_repo_check is enabled by default.")
    return hints


def build_run_result_payload(
    config: dict[str, Any],
    request_started: float,
    returncode: int,
    stdout_text: str,
    stderr_text: str,
    request_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = output_state(stdout_text, stderr_text)
    stage = result_stage(returncode, stdout_text, stderr_text)
    process_ok = returncode == 0
    ok = process_ok and stage != "empty_output"
    return {
        "ok": ok,
        "stage": stage,
        "error": empty_output_error(returncode, stdout_text, stderr_text),
        "empty_output": stage == "empty_output",
        "output_state": state,
        "process_ok": process_ok,
        "time": now_iso(),
        "duration_seconds": round(time.time() - request_started, 3),
        **run_config_summary(config),
        "returncode": returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_preview": stdout_text[:4000],
        "stderr_preview": stderr_text[:4000],
        "repo_aliases": {k: str(v) for k, v in REPO_ALIASES.items()},
        "hints": build_codex_hints(process_ok, stderr_text, stdout_text),
        "request_log": request_log,
    }
