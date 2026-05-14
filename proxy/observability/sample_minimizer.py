import argparse
import json
from pathlib import Path
from typing import Dict, List

from .replay_runner import replay_sample


def minimize_sample(sample: Dict) -> Dict:
    data = json.loads(json.dumps(sample))
    chunks: List[str] = list((data.get("raw") or {}).get("llama_chunks") or [])
    base = replay_sample(data)
    if not base.ok:
        return data
    changed = True
    while changed and len(chunks) > 1:
        changed = False
        for index in range(len(chunks)):
            candidate_chunks = chunks[:index] + chunks[index + 1 :]
            candidate = json.loads(json.dumps(data))
            candidate["raw"]["llama_chunks"] = candidate_chunks
            result = replay_sample(candidate)
            if result.ok == base.ok and result.category == base.category:
                chunks = candidate_chunks
                data = candidate
                changed = True
                break
    data["raw"]["llama_chunks"] = chunks
    data["status"] = "minimized"
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimize a captured proxy sample.")
    parser.add_argument("--sample", required=True, help="Path to the sample JSON file.")
    args = parser.parse_args()
    path = Path(args.sample)
    sample = json.loads(path.read_text(encoding="utf-8"))
    minimized = minimize_sample(sample)
    out_dir = Path("proxy/test/samples/minimized")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / path.name
    out_path.write_text(json.dumps(minimized, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
