"""Stage 1 entrypoint: read a Solidity file and print basic structure.

Prefer `python -m scanner scan <file>` for a full security scan.
"""

from __future__ import annotations

import sys
from pathlib import Path

from scanner.engine import scan_file, summarize_contract


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0]) if args else Path("contracts/example.sol")
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    result = scan_file(path)
    for line in summarize_contract(result):
        print(line)
    return 0 if not result.compiler_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
