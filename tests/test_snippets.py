from pathlib import Path

from scanner.engine import scan_file
from scanner.snippets import extract_snippet
from tests.conftest import CONTRACTS


def test_extract_snippet_window() -> None:
    source = "\n".join(f"line{i}" for i in range(1, 12))
    text, start = extract_snippet(source, 1, context=2)
    assert start == 1
    assert text.splitlines()[0] == "line1"
    text, start = extract_snippet(source, 11, context=2)
    assert start == 9
    assert "line11" in text


def test_reentrancy_finding_includes_source() -> None:
    result = scan_file(CONTRACTS / "vulnerable" / "Reentrancy.sol")
    hit = next(f for f in result.findings if f.id == "SC-REENTRANCY-001")
    assert hit.snippet
    assert ".call" in hit.snippet
    assert hit.snippet_start_line >= 1
    assert hit.location.line >= hit.snippet_start_line
    assert "Reentrancy.sol" in hit.location.file or hit.location.file.endswith("Reentrancy.sol")
