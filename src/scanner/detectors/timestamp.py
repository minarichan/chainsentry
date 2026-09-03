"""Detect block.timestamp / now used as a protocol time gate (SWC-116)."""

from __future__ import annotations

from scanner.ast_utils import identifier_name, is_block_member, node_offset, walk
from scanner.models import Contract, Finding, Function, Severity

# Caller-supplied expiry is the Uniswap `ensure(deadline)` pattern, not a time gate.
_COMPARE_OPS = {">", "<", ">=", "<=", "==", "!="}


def _is_timestamp(node: dict) -> bool:
    if is_block_member(node, "timestamp"):
        return True
    return node.get("nodeType") == "Identifier" and node.get("name") == "now"


def _timestamp_offsets(root: dict) -> set[int]:
    return {node_offset(n) for n in walk(root) if _is_timestamp(n)}


def _deadline_param_offsets(fn: Function) -> set[int]:
    """Offsets of timestamp nodes compared only to a function parameter."""
    param_names = {p.name for p in fn.parameters if p.name}
    if not param_names:
        return set()
    covered: set[int] = set()
    for node in walk(fn.ast):
        if node.get("nodeType") != "BinaryOperation" or node.get("operator") not in _COMPARE_OPS:
            continue
        left = node.get("leftExpression") or {}
        right = node.get("rightExpression") or {}
        left_ts = _timestamp_offsets(left)
        right_ts = _timestamp_offsets(right)
        if left_ts and not right_ts:
            other = right
            ts_offsets = left_ts
        elif right_ts and not left_ts:
            other = left
            ts_offsets = right_ts
        else:
            continue
        if other.get("nodeType") == "Identifier" and other.get("name") in param_names:
            covered.update(ts_offsets)
            continue
        # `deadline >= block.timestamp` where deadline is Identifier — already handled.
        # Also allow a param wrapped in nothing else.
        name = identifier_name(other) if other.get("nodeType") == "Identifier" else None
        if name in param_names:
            covered.update(ts_offsets)
    return covered


class TimestampDetector:
    id = "SC-TIMESTAMP-001"
    title = "Timestamp Dependence"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            if fn.is_constructor or fn.is_receive or fn.is_fallback:
                continue
            if fn.mutability in {"view", "pure"}:
                continue

            hits = [n for n in walk(fn.ast) if _is_timestamp(n)]
            if not hits:
                continue
            remaining = {node_offset(n) for n in hits} - _deadline_param_offsets(fn)
            if not remaining:
                continue

            location_node = next(n for n in hits if node_offset(n) in remaining)
            findings.append(
                Finding(
                    id=self.id,
                    title=self.title,
                    severity=Severity.MEDIUM,
                    confidence=70,
                    description=(
                        f"`{fn.name}()` uses `block.timestamp` (or `now`) as a protocol time gate "
                        f"(compared to storage or used in arithmetic), not merely a caller deadline. "
                        f"Validators can nudge timestamps within protocol limits."
                    ),
                    location=contract.location_of(location_node),
                    function=fn.name,
                    recommendation=(
                        "Do not use timestamps for randomness or tight fairness windows. "
                        "Caller-supplied `deadline` checks are fine; prefer oracles when the "
                        "time gate decides a winner or payout."
                    ),
                    classification="SWC-116",
                    contract=contract.name,
                )
            )
        return findings
