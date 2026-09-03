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
    source = (CONTRACTS / "vulnerable" / "Reentrancy.sol").read_text(encoding="utf-8")
    assert ".call" in source.splitlines()[hit.location.line - 1]


def test_randomness_highlights_the_entropy_line() -> None:
    result = scan_file(CONTRACTS / "vulnerable" / "Randomness.sol")
    hit = next(f for f in result.findings if f.id == "SC-RANDOMNESS-001")
    source = (CONTRACTS / "vulnerable" / "Randomness.sol").read_text(encoding="utf-8")
    line = source.splitlines()[hit.location.line - 1]
    assert "keccak256" in line
    assert "function enter" not in (hit.snippet or "")


def test_inherited_finding_uses_parent_file_and_call_line() -> None:
    from scanner.compiler import compile_sources
    from scanner.engine import _run_detectors

    base = """pragma solidity ^0.8.0;
contract SplitBase {
    mapping(address => uint256) public balances;
    function withdraw() public {
        uint256 amount = balances[msg.sender];
        (bool sent, ) = msg.sender.call{value: amount}("");
        require(sent, "failed");
        balances[msg.sender] = 0;
    }
}
"""
    child = """pragma solidity ^0.8.0;
import "./SplitBase.sol";
contract SplitChild is SplitBase {}
"""
    compilation = compile_sources(
        {"SplitBase.sol": base, "SplitChild.sol": child},
        filename="SplitChild.sol",
    )
    assert compilation.success, compilation.errors
    result = _run_detectors(compilation)
    hit = next(f for f in result.findings if f.id == "SC-REENTRANCY-001")
    assert hit.function == "withdraw"
    assert hit.location.file.replace("\\", "/").endswith("SplitBase.sol")
    assert ".call" in (hit.snippet or "")
    assert ".call" in base.splitlines()[hit.location.line - 1]
    assert "contract SplitChild" not in (hit.snippet or "")
