from pathlib import Path

from scanner.compiler import compile_file
from scanner.parser import parse_compilation

ROOT = Path(__file__).resolve().parents[1]


def test_parser_extracts_structure() -> None:
    compiled = compile_file(ROOT / "contracts" / "example.sol")
    contracts = parse_compilation(compiled)
    assert len(contracts) == 1
    example = contracts[0]
    names = {fn.name for fn in example.functions}
    assert "deposit" in names
    assert "withdraw" in names
    assert "transfer" in names
    assert "setOwner" in names
    vars_ = {v.name for v in example.state_variables}
    assert {"owner", "totalDeposits", "balances"} <= vars_
    assert any(m.name == "onlyOwner" for m in example.modifiers)
    assert any(e.name == "Deposited" for e in example.events)
    deposit = example.function_by_name("deposit")
    assert deposit is not None
    assert deposit.visibility == "external"
    assert deposit.mutability == "payable"
    set_owner = example.function_by_name("setOwner")
    assert set_owner is not None
    assert "onlyOwner" in set_owner.modifiers


def test_interfaces_and_libraries_are_not_parsed() -> None:
    compiled = compile_file(ROOT / "contracts" / "vulnerable" / "TokenReentrancy.sol")
    contracts = parse_compilation(compiled)
    names = {c.name for c in contracts}
    assert names == {"TokenReentrancy"}
    assert all(c.kind == "contract" for c in contracts)


def test_library_is_not_parsed() -> None:
    from scanner.compiler import compile_source

    source = """pragma solidity ^0.8.0;
library Math { function add(uint a, uint b) internal pure returns (uint) { return a + b; } }
contract UsesMath { function f() external pure returns (uint) { return Math.add(1, 2); } }
"""
    compiled = compile_source(source, filename="LibUser.sol")
    contracts = parse_compilation(compiled)
    assert {c.name for c in contracts} == {"UsesMath"}
