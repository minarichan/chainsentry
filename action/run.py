"""Scan Solidity files for the GitHub Action (not an exploit generator)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from scanner.cli import SEVERITY_ORDER
from scanner.engine import scan_file
from scanner.reporting.markdown_report import render_markdown
from scanner.reporting.sarif_report import render_sarif_many

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "lib",
    "out",
    "cache",
    "dist",
    "artifacts",
    "broadcast",
    "dependencies",
    "__pycache__",
}


def iter_sol_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".sol" else []
    files: list[Path] = []
    for path in root.rglob("*.sol"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def fail_on_hit(results, minimum: str) -> bool:
    threshold = SEVERITY_ORDER[minimum]
    for result in results:
        if any(SEVERITY_ORDER[finding.severity.value] <= threshold for finding in result.findings):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ChainSentry CI scan")
    parser.add_argument("--path", default=".", help="Solidity file or directory")
    parser.add_argument("--output", default="reports", help="Report directory")
    parser.add_argument(
        "--fail-on",
        default="",
        choices=["", "critical", "high", "medium", "low"],
        help="Exit 1 if findings at this severity or worse exist",
    )
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 2

    files = iter_sol_files(root)
    if not files:
        print(f"No .sol files under {root}")
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        (out / "chainsentry.sarif").write_text(
            json.dumps(render_sarif_many([]), indent=2), encoding="utf-8"
        )
        (out / "chainsentry.md").write_text("# ChainSentry\n\nNo Solidity files found.\n", encoding="utf-8")
        return 0

    results = []
    for file in files:
        print(f"Scanning {file}")
        result = scan_file(str(file))
        result.network = "Local"
        results.append(result)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    sarif_path = out / "chainsentry.sarif"
    md_path = out / "chainsentry.md"
    sarif_path.write_text(json.dumps(render_sarif_many(results), indent=2), encoding="utf-8")
    md_path.write_text(
        "\n\n---\n\n".join(render_markdown(item) for item in results),
        encoding="utf-8",
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        Path(summary).write_text(md_path.read_text(encoding="utf-8")[:65000], encoding="utf-8")

    print(f"Wrote {sarif_path}")
    print(f"Wrote {md_path}")

    if args.fail_on and fail_on_hit(results, args.fail_on):
        print(f"Failing: findings at {args.fail_on} or worse", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
