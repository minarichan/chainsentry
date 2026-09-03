"""SARIF 2.1.0 export for GitHub Code Scanning and other SARIF consumers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scanner.detectors import all_detectors
from scanner.models import ScanResult, Severity

SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

_LEVEL = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}

_SECURITY_SEVERITY = {
    Severity.CRITICAL: "9.0",
    Severity.HIGH: "8.0",
    Severity.MEDIUM: "5.5",
    Severity.LOW: "3.0",
    Severity.INFO: "1.0",
}


def _rules() -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for detector in all_detectors():
        rules.append(
            {
                "id": detector.id,
                "name": detector.title,
                "shortDescription": {"text": detector.title},
                "fullDescription": {"text": detector.title},
                "help": {"text": detector.title},
                "defaultConfiguration": {"level": "warning"},
                "properties": {
                    "tags": ["security", "solidity"],
                    "precision": "medium",
                },
            }
        )
    return rules


def render_sarif(result: ScanResult) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for finding in result.findings:
        level = _LEVEL.get(finding.severity, "warning")
        uri = finding.location.file or result.filename
        region: dict[str, Any] = {"startLine": max(1, finding.location.line)}
        if finding.location.end_line:
            region["endLine"] = finding.location.end_line
        results.append(
            {
                "ruleId": finding.id,
                "level": level,
                "message": {"text": finding.description},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri.replace("\\", "/")},
                            "region": region,
                        }
                    }
                ],
                "properties": {
                    "security-severity": _SECURITY_SEVERITY.get(finding.severity, "5.0"),
                    "function": finding.function,
                    "classification": finding.classification,
                    "recommendation": finding.recommendation,
                },
            }
        )

    return {
        "$schema": SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ChainSentry",
                        "version": "0.1.0",
                        "rules": _rules(),
                    }
                },
                "results": results,
                "invocations": [
                    {
                        "executionSuccessful": not bool(result.compiler_errors),
                    }
                ],
            }
        ],
    }


def render_sarif_many(scan_results: list[ScanResult]) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    ok = True
    for item in scan_results:
        merged.extend(render_sarif(item)["runs"][0]["results"])
        if item.compiler_errors:
            ok = False
    return {
        "$schema": SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ChainSentry",
                        "version": "0.1.0",
                        "rules": _rules(),
                    }
                },
                "results": merged,
                "invocations": [{"executionSuccessful": ok}],
            }
        ],
    }


def write_sarif_report(result: ScanResult, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(render_sarif(result), indent=2), encoding="utf-8")
    return output
