"""Detect weak on-chain randomness from block attributes (SWC-120)."""

from __future__ import annotations

from scanner.ast_utils import is_block_member, walk
from scanner.models import Contract, Finding, Severity

WEAK_MEMBERS = {"timestamp", "difficulty", "number", "prevrandao", "coinbase", "gaslimit"}


def _is_weak_source(node: dict) -> bool:
    if node.get("nodeType") == "Identifier" and node.get("name") == "now":
        return True
    if node.get("nodeType") == "FunctionCall":
        expr = node.get("expression") or {}
        if expr.get("name") == "blockhash":
            return True
    for member in WEAK_MEMBERS:
        if is_block_member(node, member):
            return True
    return False


def _rng_node(hits: list[dict], fn_ast: dict) -> dict:
    """Prefer the block attribute mixed into keccak / encodePacked, not an earlier hit."""
    for node in walk(fn_ast):
        if node.get("nodeType") != "FunctionCall":
            continue
        name = (node.get("expression") or {}).get("name")
        if name not in {"keccak256", "sha256", "abi.encodePacked"}:
            continue
        for hit in hits:
            if hit is node or any(child is hit for child in walk(node)):
                return hit
    return hits[0]


class RandomnessDetector:
    id = "SC-RANDOMNESS-001"
    title = "Weak Randomness from Block Attributes"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            hits = [n for n in walk(fn.ast) if _is_weak_source(n)]
            # Only flag when the value is mixed into arithmetic / keccak — typical RNG pattern.
            uses_hash = any(
                n.get("nodeType") == "FunctionCall"
                and (n.get("expression") or {}).get("name") in {"keccak256", "sha256", "abi.encodePacked"}
                for n in walk(fn.ast)
            )
            uses_modulo = any(
                n.get("nodeType") == "BinaryOperation" and n.get("operator") == "%"
                for n in walk(fn.ast)
            )
            if not hits:
                continue
            if not (uses_hash or uses_modulo):
                continue
            node = _rng_node(hits, fn.ast)
            findings.append(
                Finding(
                    id=self.id,
                    title=self.title,
                    severity=Severity.HIGH,
                    confidence=80,
                    description=(
                        f"`{fn.name}()` derives a 'random' value from block data "
                        f"(`timestamp`, `difficulty`, `number`, `prevrandao`, or `blockhash`). "
                        f"Validators and callers can bias or predict this value."
                    ),
                    location=contract.location_of(node),
                    function=fn.name,
                    recommendation=(
                        "Use a verifiable random function (Chainlink VRF or equivalent). "
                        "Never treat block attributes as secret entropy."
                    ),
                    classification="SWC-120",
                    contract=contract.name,
                )
            )
        return findings
