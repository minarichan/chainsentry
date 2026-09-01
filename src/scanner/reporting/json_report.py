"""Write a machine-readable scan report."""

from __future__ import annotations

import json
from pathlib import Path

from scanner.models import ScanResult


def write_json_report(result: ScanResult, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return output
