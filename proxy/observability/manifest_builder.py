import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .failure_classifier import classify_failure_sample
from .sample_schema import CURRENT_SCHEMA_VERSION, load_sample

SAMPLE_ROOT = Path("proxy/test/samples")
MANIFEST_PATH = Path("proxy/test/manifests/error_index.json")
STATUSES = ("quarantine", "minimized", "approved", "rejected")


def _generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_manifest(sample_root: Path = SAMPLE_ROOT, manifest_path: Path = MANIFEST_PATH) -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    for status in STATUSES:
        status_dir = sample_root / status
        if not status_dir.exists():
            continue
        for path in sorted(status_dir.glob("*.json")):
            try:
                sample = load_sample(path.read_text(encoding="utf-8")).to_dict()
            except Exception:
                continue
            classification = classify_failure_sample(sample)
            sample["category"] = sample.get("category") or classification.category
            cases.append(
                {
                    "id": sample.get("id") or path.stem,
                    "file": path.as_posix(),
                    "category": sample.get("category", classification.category),
                    "status": sample.get("status", status),
                    "fingerprint": sample.get("fingerprint", ""),
                    "timestamp": sample.get("timestamp", ""),
                    "replayable": classification.replayable,
                }
            )
    cases.sort(key=lambda item: (item.get("timestamp", ""), item.get("file", "")), reverse=True)
    manifest = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "generated_at": _generated_at(),
        "cases": cases,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the proxy failure manifest.")
    parser.parse_args()
    build_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
