from pathlib import Path

from action.run import fail_on_hit, iter_sol_files
from scanner.models import Finding, Location, ScanResult, ScoreCard, Severity
from scanner.reporting.sarif_report import render_sarif_many


def test_iter_sol_skips_vendor_dirs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    keep = tmp_path / "src" / "Token.sol"
    keep.write_text("pragma solidity ^0.8.0; contract Token {}", encoding="utf-8")
    vendor = tmp_path / "node_modules" / "oz"
    vendor.mkdir(parents=True)
    (vendor / "Skip.sol").write_text("pragma solidity ^0.8.0; contract Skip {}", encoding="utf-8")
    found = iter_sol_files(tmp_path)
    assert found == [keep]


def test_iter_sol_single_file(tmp_path: Path) -> None:
    sol = tmp_path / "A.sol"
    sol.write_text("pragma solidity ^0.8.0; contract A {}", encoding="utf-8")
    assert iter_sol_files(sol) == [sol]


def test_fail_on_high() -> None:
    hit = ScanResult(
        contracts=[],
        findings=[
            Finding(
                id="SC-TXORIGIN-001",
                title="tx.origin",
                severity=Severity.HIGH,
                confidence=80,
                description="x",
                location=Location(file="A.sol", line=1),
                function=None,
                recommendation="y",
                classification="SWC-115",
            )
        ],
        scorecard=ScoreCard(score=80, high=1),
        surfaces=[],
        filename="A.sol",
        solc_version="0.8.20",
        source="",
    )
    clean = ScanResult(
        contracts=[],
        findings=[],
        scorecard=ScoreCard(score=100),
        surfaces=[],
        filename="B.sol",
        solc_version="0.8.20",
        source="",
    )
    assert fail_on_hit([hit], "high") is True
    assert fail_on_hit([clean], "high") is False


def test_sarif_many_merges_results() -> None:
    payload = render_sarif_many([])
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["results"] == []
