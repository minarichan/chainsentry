from pathlib import Path

from scanner.engine import scan_file, summarize_contract

ROOT = Path(__file__).resolve().parents[1]


def test_example_contract_summary() -> None:
    result = scan_file(ROOT / "contracts" / "example.sol")
    assert result.compiler_errors == []
    assert result.contracts
    example = result.contracts[0]
    assert example.name == "Example"
    assert len(example.functions) >= 4
    assert len(example.state_variables) >= 3
    text = "\n".join(summarize_contract(result))
    assert "Contract: Example" in text
    assert "Functions:" in text
    assert "State Variables:" in text
