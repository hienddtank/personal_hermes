#!/usr/bin/env python3
"""Generate structure.md for this workspace."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_EXCLUDES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "firecrawl-data",
    "firecrawl-src",
    "open-webui-data",
}

DEFAULT_EXCLUDE_PATHS = {
    "hermes-home/cache",
    "hermes-home/logs",
    "hermes-home/sessions",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh structure.md with an ASCII tree of the workspace."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Root directory to document. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("structure.md"),
        help="Markdown file to write. Defaults to structure.md.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum directory depth to print below root. Defaults to 4.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Name or relative path to exclude. Can be passed more than once.",
    )
    return parser.parse_args()


def normalized_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_exclude(path: Path, root: Path, excludes: set[str]) -> bool:
    rel = normalized_relative(path, root) if path != root else ""
    return path.name in excludes or rel in excludes


def sorted_children(path: Path, root: Path, excludes: set[str]) -> list[Path]:
    children = [child for child in path.iterdir() if not should_exclude(child, root, excludes)]
    return sorted(children, key=lambda child: (not child.is_dir(), child.name.lower()))


def render_tree(root: Path, max_depth: int, excludes: set[str]) -> list[str]:
    lines = [f"{root}\\"]

    def walk(directory: Path, prefix: str, depth: int) -> None:
        if depth >= max_depth:
            return

        children = sorted_children(directory, root, excludes)
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            connector = "`-- " if is_last else "|-- "
            suffix = "\\" if child.is_dir() else ""
            lines.append(f"{prefix}{connector}{child.name}{suffix}")

            if child.is_dir():
                extension = "    " if is_last else "|   "
                walk(child, prefix + extension, depth + 1)

    walk(root, "", 0)
    return lines


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output

    excludes = set(DEFAULT_EXCLUDES)
    excludes.update(DEFAULT_EXCLUDE_PATHS)
    excludes.update(item.replace("\\", "/").strip("/") for item in args.exclude)

    lines = [
        "# Workspace Structure",
        "",
        f"Generated from `{root}`.",
        "",
        "Excluded by default: "
        + ", ".join(f"`{item}`" for item in sorted(excludes))
        + ".",
        "",
        "```text",
        *render_tree(root, args.max_depth, excludes),
        "```",
        "",
        "Refresh with:",
        "",
        "```powershell",
        "python update_structure.py",
        "```",
        "",
    ]

    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
