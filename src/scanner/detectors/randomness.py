"""Detect weak on-chain randomness from block attributes (SWC-120)."""

from __future__ import annotations

from scanner.ast_utils import is_block_member, node_line, walk
from scanner.models import Contract, Finding, Location, Severity

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
            node = hits[0]
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
                    location=Location(
                        file=contract.filename,
                        line=node_line(contract.source, node),
                    ),
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
