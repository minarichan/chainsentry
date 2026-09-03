"""Detect weak on-chain randomness from block attributes (SWC-120)."""

from __future__ import annotations

from scanner.ast_utils import is_block_member, walk
from scanner.models import Contract, Finding, Severity

WEAK_MEMBERS = {"timestamp", "difficulty", "number", "prevrandao", "coinbase", "gaslimit"}
HASH_SYMBOLS = {"keccak256", "sha256", "ripemd160", "abi.encodepacked"}


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


def _call_symbol(node: dict) -> str:
    expr = node.get("expression") or {}
    if expr.get("nodeType") == "Identifier":
        return str(expr.get("name") or "").lower()
    if expr.get("nodeType") == "MemberAccess":
        base = expr.get("expression") or {}
        member = str(expr.get("memberName") or "").lower()
        if str(base.get("name") or "").lower() == "abi":
            return f"abi.{member}"
        return member
    return ""


def _contains(root: dict, target: dict) -> bool:
    return root is target or any(child is target for child in walk(root))


def _entropy_mix_nodes(fn_ast: dict, hits: list[dict]) -> list[dict]:
    """Hash / modulo nodes that actually consume a weak block attribute."""
    mixed: list[dict] = []
    for node in walk(fn_ast):
        ntype = node.get("nodeType")
        consumes = False
        if ntype == "FunctionCall" and _call_symbol(node) in HASH_SYMBOLS:
            consumes = True
        elif ntype == "BinaryOperation" and node.get("operator") == "%":
            consumes = True
        if not consumes:
            continue
        if any(_contains(node, hit) for hit in hits):
            mixed.append(node)
    return mixed


def _rng_node(mix_nodes: list[dict], hits: list[dict]) -> dict:
    """Highlight keccak / encodePacked (or modulo), not an earlier timestamp check."""
    for node in mix_nodes:
        if node.get("nodeType") == "FunctionCall" and _call_symbol(node) in HASH_SYMBOLS:
            return node
    if mix_nodes:
        return mix_nodes[0]
    return hits[0]


class RandomnessDetector:
    id = "SC-RANDOMNESS-001"
    title = "Weak Randomness from Block Attributes"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            hits = [n for n in walk(fn.ast) if _is_weak_source(n)]
            if not hits:
                continue
            mix_nodes = _entropy_mix_nodes(fn.ast, hits)
            if not mix_nodes:
                continue
            node = _rng_node(mix_nodes, hits)
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
