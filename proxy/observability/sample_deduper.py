from pathlib import Path
from typing import Iterable

from .sample_schema import load_sample


def existing_fingerprints(paths: Iterable[Path]) -> set[str]:
    fingerprints: set[str] = set()
    for path in paths:
        try:
            sample = load_sample(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        fingerprint = sample.data.get("fingerprint")
        if fingerprint:
            fingerprints.add(str(fingerprint))
    return fingerprints


def is_duplicate_sample(directory: Path, fingerprint: str) -> bool:
    if not directory.exists():
        return False
    return fingerprint in existing_fingerprints(directory.glob("*.json"))

