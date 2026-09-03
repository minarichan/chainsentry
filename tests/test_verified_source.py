from scanner.etherscan import (
    SourceNotVerifiedError,
    VerifiedContract,
    _from_blockscout_payload,
    fetch_verified_source,
)


def test_blockscout_payload_to_verified_contract() -> None:
    payload = {
        "is_verified": True,
        "name": "Foo",
        "file_path": "src/Foo.sol",
        "compiler_version": "v0.8.20+commit.a1b79de6",
        "source_code": "pragma solidity ^0.8.0; contract Foo {}",
        "optimization_enabled": True,
        "optimization_runs": 200,
        "evm_version": "paris",
        "compiler_settings": {"viaIR": True, "optimizer": {"enabled": True, "runs": 200}},
        "additional_sources": [],
        "implementations": [],
    }
    verified = _from_blockscout_payload("0x0000000000000000000000000000000000000001", payload)
    assert verified.name == "Foo"
    assert verified.via_ir is True
    assert verified.optimizer == {"enabled": True, "runs": 200}
    assert "src/Foo.sol" in verified.sources
    assert verified.extra["source"] == "blockscout"


def test_fetch_falls_through_to_blockscout(monkeypatch) -> None:
    monkeypatch.setattr("scanner.etherscan._api_key", lambda explicit=None: "")
    monkeypatch.setattr(
        "scanner.etherscan.fetch_from_sourcify",
        lambda address, chain_id=None: (_ for _ in ()).throw(
            SourceNotVerifiedError("not on sourcify")
        ),
    )
    impl = VerifiedContract(
        address="0x1",
        name="FromBlockscout",
        source="pragma solidity ^0.8.0; contract FromBlockscout {}",
        compiler_version="v0.8.20+commit.a1b79de6",
        solc_version="0.8.20",
        verified=True,
        extra={"source": "blockscout"},
    )
    monkeypatch.setattr("scanner.etherscan.fetch_from_blockscout", lambda address, chain_id=None: impl)
    got = fetch_verified_source("0x0000000000000000000000000000000000000001")
    assert got.name == "FromBlockscout"


def test_fetch_uses_etherscan_when_key_present(monkeypatch) -> None:
    monkeypatch.setattr("scanner.etherscan._api_key", lambda explicit=None: "test-key")
    monkeypatch.setattr(
        "scanner.etherscan.fetch_from_sourcify",
        lambda address, chain_id=None: (_ for _ in ()).throw(SourceNotVerifiedError("not on sourcify")),
    )
    impl = VerifiedContract(
        address="0x1",
        name="FromEtherscan",
        source="pragma solidity ^0.8.0; contract FromEtherscan {}",
        compiler_version="v0.8.20+commit.a1b79de6",
        solc_version="0.8.20",
        verified=True,
        extra={"source": "etherscan"},
    )
    monkeypatch.setattr("scanner.etherscan.fetch_from_etherscan", lambda address, api_key=None, chain_id=None: impl)

    def fail_blockscout(address, chain_id=None):
        raise AssertionError("Blockscout should not run if Etherscan succeeded")

    monkeypatch.setattr("scanner.etherscan.fetch_from_blockscout", fail_blockscout)
    got = fetch_verified_source("0x0000000000000000000000000000000000000001")
    assert got.name == "FromEtherscan"


def test_fetch_error_mentions_missing_etherscan_key(monkeypatch) -> None:
    monkeypatch.setattr("scanner.etherscan._api_key", lambda explicit=None: "")
    monkeypatch.setattr(
        "scanner.etherscan.fetch_from_sourcify",
        lambda address, chain_id=None: (_ for _ in ()).throw(SourceNotVerifiedError("not on sourcify")),
    )
    monkeypatch.setattr(
        "scanner.etherscan.fetch_from_blockscout",
        lambda address, chain_id=None: (_ for _ in ()).throw(SourceNotVerifiedError("not on blockscout")),
    )
    try:
        fetch_verified_source("0x0000000000000000000000000000000000000001")
        raise AssertionError("expected SourceNotVerifiedError")
    except SourceNotVerifiedError as exc:
        message = str(exc)
        assert "Sourcify" in message
        assert "Blockscout" in message
        assert "ETHERSCAN_API_KEY" in message
        assert "example address" in message
        assert "bytecode-only" not in message
        assert "0x0000000000000000000000000000000000000001" not in message


def test_etherscan_hourly_cap_skips_to_blockscout(monkeypatch) -> None:
    from scanner.etherscan import EtherscanBudgetError, reset_etherscan_budget_for_tests

    monkeypatch.setenv("ETHERSCAN_MAX_PER_HOUR", "1")
    reset_etherscan_budget_for_tests()
    monkeypatch.setattr("scanner.etherscan._api_key", lambda explicit=None: "test-key")
    monkeypatch.setattr(
        "scanner.etherscan.fetch_from_sourcify",
        lambda address, chain_id=None: (_ for _ in ()).throw(SourceNotVerifiedError("not on sourcify")),
    )

    def cap_etherscan(address, api_key=None, chain_id=None):
        raise EtherscanBudgetError("Etherscan hourly cap reached; trying other explorers.")

    monkeypatch.setattr("scanner.etherscan.fetch_from_etherscan", cap_etherscan)
    impl = VerifiedContract(
        address="0x1",
        name="FromBlockscout",
        source="pragma solidity ^0.8.0; contract C {}",
        compiler_version="0.8.20",
        solc_version="0.8.20",
        verified=True,
    )
    monkeypatch.setattr("scanner.etherscan.fetch_from_blockscout", lambda address, chain_id=None: impl)
    got = fetch_verified_source("0x0000000000000000000000000000000000000001")
    assert got.name == "FromBlockscout"
    reset_etherscan_budget_for_tests()


def test_scan_verified_ignores_extra_contracts_in_metadata() -> None:
    from scanner.engine import scan_verified

    factory = """pragma solidity ^0.8.0;
contract Factory {
    address public owner;
    constructor() { owner = msg.sender; }
    function setOwner(address next) external {
        require(msg.sender == owner, "not owner");
        owner = next;
    }
}
"""
    token = """pragma solidity ^0.8.0;
contract TestERC20 {
    mapping(address => uint256) public balanceOf;
    function mint(address to, uint256 amount) public {
        balanceOf[to] += amount;
    }
}
"""
    verified = VerifiedContract(
        address="0x1111111111111111111111111111111111111111",
        name="Factory",
        source=factory,
        compiler_version="v0.8.20+commit.a1b79de6",
        solc_version="0.8.20",
        verified=True,
        sources={
            "contracts/Factory.sol": factory,
            "contracts/test/TestERC20.sol": token,
        },
        primary_file="contracts/Factory.sol",
    )
    result = scan_verified(verified)
    assert {c.name for c in result.contracts} == {"Factory"}
    assert "SC-ACCESS-001" not in {f.id for f in result.findings}


def test_scan_verified_still_analyzes_inherited_methods() -> None:
    from pathlib import Path

    from scanner.engine import scan_verified

    source = (Path(__file__).resolve().parents[1] / "contracts" / "vulnerable" / "InheritedReentrancy.sol").read_text(
        encoding="utf-8"
    )
    verified = VerifiedContract(
        address="0x1111111111111111111111111111111111111112",
        name="InheritedReentrancy",
        source=source,
        compiler_version="v0.8.20+commit.a1b79de6",
        solc_version="0.8.20",
        verified=True,
        sources={"InheritedReentrancy.sol": source},
        primary_file="InheritedReentrancy.sol",
    )
    result = scan_verified(verified)
    hits = [f for f in result.findings if f.id == "SC-REENTRANCY-001"]
    assert len(hits) == 1
    assert hits[0].function == "withdraw"
