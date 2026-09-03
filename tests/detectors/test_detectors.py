from pathlib import Path

from scanner.engine import scan_file
from scanner.models import Finding, Location, Severity
from scanner.scoring import compute_score, verdict_from_counts
from tests.conftest import CONTRACTS

VULN = CONTRACTS / "vulnerable"
SAFE = CONTRACTS / "safe"


def _ids(path: Path) -> set[str]:
    return {f.id for f in scan_file(path).findings}


def test_reentrancy_detected() -> None:
    assert "SC-REENTRANCY-001" in _ids(VULN / "Reentrancy.sol")
    assert "SC-REENTRANCY-002" not in _ids(VULN / "Reentrancy.sol")


def test_safe_reentrancy_no_false_positive() -> None:
    ids = _ids(SAFE / "SafeReentrancy.sol")
    assert "SC-REENTRANCY-001" not in ids
    assert "SC-REENTRANCY-002" not in ids


def test_tx_origin_detected() -> None:
    ids = _ids(VULN / "TxOrigin.sol")
    assert "SC-TXORIGIN-001" in ids
    assert "SC-ACCESS-001" not in ids


def test_unchecked_call_detected() -> None:
    assert "SC-UNCHECKED-001" in _ids(VULN / "UncheckedCall.sol")


def test_delegatecall_detected() -> None:
    assert "SC-DELEGATECALL-001" in _ids(VULN / "DelegateCall.sol")


def test_reentrancy_covers_delegatecall_on_same_function() -> None:
    from scanner.engine import scan_source

    source = """pragma solidity ^0.8.0;
contract Both {
    mapping(address => uint256) public balances;
    function execute(address target) public {
        (bool ok, ) = target.delegatecall("");
        require(ok);
        balances[msg.sender] = 0;
    }
}
"""
    result = scan_source(source, filename="Both.sol")
    ids = {f.id for f in result.findings}
    assert "SC-REENTRANCY-001" in ids
    assert "SC-DELEGATECALL-001" not in ids


def test_access_control_detected() -> None:
    assert "SC-ACCESS-001" in _ids(VULN / "AccessControl.sol")


def test_safe_access_control_no_false_positive() -> None:
    assert "SC-ACCESS-001" not in _ids(SAFE / "SafeAccessControl.sol")


def test_amm_mint_not_flagged() -> None:
    assert "SC-ACCESS-001" not in _ids(SAFE / "AmmMint.sol")


def test_admin_mint_flagged() -> None:
    assert "SC-ACCESS-001" in _ids(VULN / "AdminMint.sol")


def test_timestamp_detected() -> None:
    assert "SC-TIMESTAMP-001" in _ids(VULN / "Timestamp.sol")


def test_swap_deadline_not_flagged() -> None:
    assert "SC-TIMESTAMP-001" not in _ids(SAFE / "SwapDeadline.sol")


def test_token_reentrancy_detected() -> None:
    assert "SC-REENTRANCY-001" in _ids(VULN / "TokenReentrancy.sol")


def test_safe_token_reentrancy_no_false_positive() -> None:
    assert "SC-REENTRANCY-001" not in _ids(SAFE / "SafeTokenReentrancy.sol")


def test_cross_function_reentrancy_detected() -> None:
    result = scan_file(VULN / "CrossFunctionReentrancy.sol")
    ids = {f.id for f in result.findings}
    assert "SC-REENTRANCY-002" in ids
    assert "SC-REENTRANCY-001" not in ids
    hit = next(f for f in result.findings if f.id == "SC-REENTRANCY-002")
    assert hit.function == "harvest"
    assert "claim()" in hit.description


def test_safe_cross_function_reentrancy_no_false_positive() -> None:
    ids = _ids(SAFE / "SafeCrossFunctionReentrancy.sol")
    assert "SC-REENTRANCY-002" not in ids
    assert "SC-REENTRANCY-001" not in ids


def test_inherited_storage_reentrancy_detected() -> None:
    result = scan_file(VULN / "InheritedReentrancy.sol")
    hits = [f for f in result.findings if f.id == "SC-REENTRANCY-001"]
    assert len(hits) == 1
    assert hits[0].contract == "InheritedReentrancy"
    assert hits[0].function == "withdraw"
    assert not any(s.contract == "VaultStorage" and s.name == "withdraw" for s in result.surfaces)


def test_inherited_base_body_not_double_reported() -> None:
    result = scan_file(VULN / "InheritedBaseReentrancy.sol")
    hits = [f for f in result.findings if f.id == "SC-REENTRANCY-001"]
    assert len(hits) == 1
    assert hits[0].contract == "ChildReentrancy"
    assert hits[0].function == "withdraw"


def test_safe_inherited_reentrancy_no_false_positive() -> None:
    ids = _ids(SAFE / "SafeInheritedReentrancy.sol")
    assert "SC-REENTRANCY-001" not in ids
    assert "SC-REENTRANCY-002" not in ids


def test_interface_not_on_attack_surface() -> None:
    result = scan_file(VULN / "TokenReentrancy.sol")
    assert {c.name for c in result.contracts} == {"TokenReentrancy"}
    assert {s.contract for s in result.surfaces} == {"TokenReentrancy"}
    assert not any(s.name == "transferFrom" for s in result.surfaces)


def test_selfdestruct_detected() -> None:
    ids = _ids(VULN / "SelfDestruct.sol")
    assert "SC-SELFDESTRUCT-001" in ids
    assert "SC-ACCESS-001" not in ids


def test_randomness_detected() -> None:
    ids = _ids(VULN / "Randomness.sol")
    assert "SC-RANDOMNESS-001" in ids
    assert "SC-TIMESTAMP-001" not in ids
    assert "SC-ACCESS-001" not in ids


def test_unchecked_erc20_detected() -> None:
    assert "SC-ERC20-001" in _ids(VULN / "UncheckedErc20.sol")


def test_safe_erc20_return_no_false_positive() -> None:
    assert "SC-ERC20-001" not in _ids(SAFE / "SafeErc20Return.sol")


def test_unprotected_initialize_detected() -> None:
    ids = _ids(VULN / "UnprotectedInitialize.sol")
    assert "SC-INIT-001" in ids
    assert "SC-ACCESS-001" not in ids


def test_safe_initialize_no_false_positive() -> None:
    assert "SC-INIT-001" not in _ids(SAFE / "SafeInitialize.sol")


def test_arbitrary_transfer_from_detected() -> None:
    assert "SC-TRANSFERFROM-001" in _ids(VULN / "ArbitraryTransferFrom.sol")


def test_safe_transfer_from_no_false_positive() -> None:
    assert "SC-TRANSFERFROM-001" not in _ids(SAFE / "SafeTransferFrom.sol")


def test_token_reentrancy_not_arbitrary_from() -> None:
    assert "SC-TRANSFERFROM-001" not in _ids(VULN / "TokenReentrancy.sol")


def test_duplicate_findings_collapsed() -> None:
    from scanner.engine import _dedupe_findings

    shared = dict(
        id="SC-RANDOMNESS-001",
        title="Weak Randomness from Block Attributes",
        severity=Severity.HIGH,
        confidence=80,
        description="same",
        location=Location(file="Game.sol", line=997),
        function="_generateSalt",
        recommendation="vrf",
        classification="SWC-120",
    )
    first = Finding(**{**shared, "location": Location(file="src/A.sol", line=997)}, contract="RelayA")
    second = Finding(**{**shared, "location": Location(file="src/B.sol", line=997)}, contract="RelayB")
    third = Finding(**{**shared, "location": Location(file="src/C.sol", line=997)}, contract="RelayC")
    collapsed = _dedupe_findings([first, second, third])
    assert len(collapsed) == 1
    assert collapsed[0].contract == "RelayA, RelayB, RelayC"


def test_scoring_penalizes_high_findings() -> None:
    findings = [
        Finding(
            id="SC-REENTRANCY-001",
            title="x",
            severity=Severity.HIGH,
            confidence=90,
            description="",
            location=Location(file="A.sol", line=1),
            function="withdraw",
            recommendation="",
            classification="SWC-107",
        ),
        Finding(
            id="SC-TIMESTAMP-001",
            title="y",
            severity=Severity.MEDIUM,
            confidence=70,
            description="",
            location=Location(file="A.sol", line=2),
            function="bid",
            recommendation="",
            classification="SWC-116",
        ),
    ]
    card = compute_score(findings)
    assert card.high == 1
    assert card.medium == 1
    assert card.score == 100 - 15 - 7
    assert card.verdict == "issues"
    assert card.verdict_label == "Issues found"
    assert card.score_kind == "heuristic_penalty"
    reentrancy = next(c for c in card.categories if c.name == "Reentrancy")
    assert reentrancy.finding_count == 1


def test_verdict_follows_severity_mix_not_penalty() -> None:
    assert verdict_from_counts(critical=0, high=0, medium=0, low=0, info=0) == (
        "clean",
        "No detector hits",
    )
    assert verdict_from_counts(critical=0, high=0, medium=2, low=0, info=0)[0] == "review"
    assert verdict_from_counts(critical=0, high=0, medium=0, low=1, info=0)[0] == "notes"
    assert verdict_from_counts(critical=0, high=0, medium=0, low=0, info=0, compiled=False)[0] == "failed"
