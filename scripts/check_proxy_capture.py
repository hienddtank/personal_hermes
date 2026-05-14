import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


def load_json_file(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def iter_json_files(path: Path) -> Iterable[Path]:
    if path.is_file() and path.suffix.lower() == ".json":
        yield path
        return
    if path.is_dir():
        yield from sorted(path.rglob("*.json"))


def summarize_logs(log_dir: Path) -> Dict[str, Any]:
    files = list(iter_json_files(log_dir))
    records = [record for record in (load_json_file(path) for path in files) if isinstance(record, dict)]
    by_stage = Counter(str(record.get("stage") or "unknown") for record in records)
    by_request = Counter(str(record.get("request_id") or "unknown") for record in records)
    return {
        "file_count": len(files),
        "record_count": len(records),
        "stages": by_stage,
        "top_request_ids": by_request.most_common(10),
        "latest_files": [path.as_posix() for path in files[-10:]],
    }


def summarize_samples(sample_root: Path) -> Dict[str, Any]:
    files = list(iter_json_files(sample_root))
    samples: List[Dict[str, Any]] = [sample for sample in (load_json_file(path) for path in files) if isinstance(sample, dict)]
    by_category = Counter(str(sample.get("category") or "UNKNOWN") for sample in samples)
    by_status = Counter(str(sample.get("status") or "unknown") for sample in samples)
    by_request = Counter(str(sample.get("request_id") or "unknown") for sample in samples)
    return {
        "file_count": len(files),
        "sample_count": len(samples),
        "categories": by_category,
        "statuses": by_status,
        "top_request_ids": by_request.most_common(10),
        "latest_files": [path.as_posix() for path in files[-10:]],
    }


def print_counter(title: str, counter: Counter) -> None:
    print(title)
    if not counter:
        print("  none")
        return
    for key, value in counter.most_common():
        print(f"  {key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan proxy JSON logs and captured failure samples.")
    parser.add_argument("--log-dir", default="log_proxy", help="Directory containing proxy JSON logs.")
    parser.add_argument(
        "--sample-root",
        default="proxy/test/samples",
        help="Directory containing quarantine/minimized/approved/rejected samples.",
    )
    parser.add_argument("--show-latest", type=int, default=5, help="How many recent files to print per section.")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    sample_root = Path(args.sample_root)
    log_summary = summarize_logs(log_dir)
    sample_summary = summarize_samples(sample_root)

    print("Proxy Log Summary")
    print(f"  log_dir: {log_dir.as_posix()}")
    print(f"  files: {log_summary['file_count']}")
    print(f"  parsed_records: {log_summary['record_count']}")
    print_counter("  stages:", log_summary["stages"])

    print("")
    print("Capture Sample Summary")
    print(f"  sample_root: {sample_root.as_posix()}")
    print(f"  files: {sample_summary['file_count']}")
    print(f"  parsed_samples: {sample_summary['sample_count']}")
    print_counter("  statuses:", sample_summary["statuses"])
    print_counter("  categories:", sample_summary["categories"])

    log_request_ids = {request_id for request_id, _ in log_summary["top_request_ids"]}
    sample_request_ids = {request_id for request_id, _ in sample_summary["top_request_ids"]}
    overlap = sorted(request_id for request_id in (log_request_ids & sample_request_ids) if request_id != "unknown")
    print("")
    print("Recent Files")
    for label, files in (("logs", log_summary["latest_files"]), ("samples", sample_summary["latest_files"])):
        print(f"  {label}:")
        for path in files[-args.show_latest :]:
            print(f"    {path}")

    print("")
    print("Request ID Overlap")
    if overlap:
        for request_id in overlap[: args.show_latest]:
            print(f"  {request_id}")
    else:
        print("  none")

    if sample_summary["sample_count"] == 0:
        print("")
        print("No captured samples found. If capture is enabled, trigger a proxy failure and rerun this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
