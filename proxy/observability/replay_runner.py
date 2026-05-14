import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from proxy.core_parts import SessionState, StreamStateMachine

from .contract_validator import ValidationResult, validate_non_stream_response, validate_sse_events
from .failure_classifier import classify_failure_sample
from .sample_schema import load_sample

DEFAULT_SAMPLE_ROOT = Path("proxy/test/samples")
DEFAULT_STATE_FILE = Path("proxy/test/manifests/replay_state.json")


@dataclass
class ReplayResult:
    ok: bool
    visible_text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    validation: Optional[ValidationResult] = None
    category: str = "UNKNOWN"


def _build_stream_events(visible_text: str) -> List[str]:
    chunk = {
        "id": "chatcmpl-replay",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "replay",
        "choices": [{"index": 0, "delta": {"content": visible_text}}],
    }
    return [f"data: {json.dumps(chunk, ensure_ascii=False)}", "data: [DONE]"]


def replay_sample(sample: Dict[str, Any]) -> ReplayResult:
    data = load_sample(sample).to_dict() if not isinstance(sample, dict) else load_sample(sample).to_dict()
    session = SessionState(request_id=str(data.get("request_id") or "replay"))
    session.policy = {"visible_reasoning": False, "hide_raw_tool_xml": True, "tools": []}
    machine = StreamStateMachine(session, session.policy)
    visible_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    for chunk in data.get("raw", {}).get("llama_chunks") or []:
        output = machine.advance_state(str(chunk))
        if output.text_delta:
            visible_parts.append(output.text_delta)
        if output.tool_call:
            tool_calls.append({"name": output.tool_call.name, "arguments": output.tool_call.arguments})
        if output.is_malformed:
            break
    flushed = machine.flush()
    if flushed.text_delta:
        visible_parts.append(flushed.text_delta)
    if flushed.tool_call:
        tool_calls.append({"name": flushed.tool_call.name, "arguments": flushed.tool_call.arguments})
    visible_text = "".join(visible_parts)
    classification = classify_failure_sample(data)
    expected_mode = ((data.get("expected_behavior") or {}).get("mode")) or "needs_review"
    validation = validate_sse_events(_build_stream_events(visible_text))
    ok = True
    if expected_mode == "must_not_leak_thinking":
        ok = "<think>" not in visible_text and "</think>" not in visible_text
    elif expected_mode == "must_complete_tool_call":
        ok = bool(tool_calls)
    elif expected_mode == "must_pass_contract":
        body = {
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": visible_text}, "finish_reason": "stop"}],
        }
        validation = validate_non_stream_response(body)
        ok = validation.ok
    elif expected_mode == "must_fail_closed":
        ok = not validation.errors or classification.category != "UNKNOWN"
    return ReplayResult(ok=ok, visible_text=visible_text, tool_calls=tool_calls, validation=validation, category=classification.category)


def replay_sample_file(path: str | Path) -> ReplayResult:
    file_path = Path(path)
    sample = json.loads(file_path.read_text(encoding="utf-8"))
    return replay_sample(sample)


def iter_sample_files(sample_root: Path) -> Iterable[Path]:
    if not sample_root.exists():
        return []
    return sorted(path for path in sample_root.rglob("*.json") if path.is_file())


def iter_approved_samples(sample_root: Path) -> Iterable[Path]:
    approved_dir = sample_root / "approved"
    if not approved_dir.exists():
        return []
    return sorted(approved_dir.glob("*.json"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_replay_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "updated_at": None, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "updated_at": None, "files": {}}
    files = data.get("files")
    if not isinstance(files, dict):
        files = {}
    return {"schema_version": 1, "updated_at": data.get("updated_at"), "files": files}


def save_replay_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now_iso()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def sample_identity(path: Path) -> str:
    try:
        sample = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path.as_posix()
    fingerprint = sample.get("fingerprint")
    if fingerprint:
        return f"{path.as_posix()}::{fingerprint}"
    sample_id = sample.get("id")
    if sample_id:
        return f"{path.as_posix()}::{sample_id}"
    return path.as_posix()


def replay_and_record(paths: Iterable[Path], state_file: Path, skip_known: bool = True) -> int:
    state = load_replay_state(state_file)
    failures = 0
    ran = 0
    skipped = 0
    for path in paths:
        key = sample_identity(path)
        if skip_known and key in state["files"]:
            skipped += 1
            print(f"{path.as_posix()}: skipped")
            continue
        result = replay_sample_file(path)
        ran += 1
        state["files"][key] = {
            "file": path.as_posix(),
            "ok": result.ok,
            "category": result.category,
            "ran_at": _utc_now_iso(),
        }
        print(f"{path.as_posix()}: ok={result.ok} category={result.category}")
        if not result.ok:
            failures += 1
    save_replay_state(state_file, state)
    print(f"summary: ran={ran} skipped={skipped} failures={failures}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay captured proxy samples offline.")
    parser.add_argument("--all-approved", action="store_true", help="Replay all approved samples.")
    parser.add_argument("--sample", help="Replay a single sample file.")
    parser.add_argument("--sample-root", default=str(DEFAULT_SAMPLE_ROOT), help="Root sample directory to scan.")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="Replay state file used to skip already-run samples.")
    parser.add_argument("--rerun-all", action="store_true", help="Ignore replay state and rerun all discovered samples.")
    args = parser.parse_args()
    sample_root = Path(args.sample_root)
    state_file = Path(args.state_file)
    if args.sample:
        result = replay_sample_file(args.sample)
        print(f"{args.sample}: ok={result.ok} category={result.category}")
        return 0 if result.ok else 1
    if args.all_approved:
        return replay_and_record(iter_approved_samples(sample_root), state_file, skip_known=not args.rerun_all)
    return replay_and_record(iter_sample_files(sample_root), state_file, skip_known=not args.rerun_all)


if __name__ == "__main__":
    raise SystemExit(main())
