"""Flag public initialize() that anyone can call (proxy takeover)."""

from __future__ import annotations

from scanner.ast_utils import function_has_modifier, has_msg_sender_check, identifier_name, walk
from scanner.detectors.access_control import ACCESS_MODIFIERS
from scanner.models import Contract, Finding, Location, Severity

INITIALIZER_MODIFIERS = {"initializer", "reinitializer", "onlyinitializing"}


def _has_initialized_guard(fn_ast: dict) -> bool:
    """True when the body checks a storage flag whose name looks like initialized."""
    for node in walk(fn_ast):
        ntype = node.get("nodeType")
        if ntype == "UnaryOperation" and node.get("operator") == "!":
            name = identifier_name(node.get("subExpression") or {})
            if name and "initializ" in name.lower():
                return True
        if ntype == "Identifier":
            continue
        if ntype == "BinaryOperation" and node.get("operator") in {"==", "!="}:
            for side in (node.get("leftExpression"), node.get("rightExpression")):
                name = identifier_name(side or {})
                if name and "initializ" in name.lower():
                    return True
    return False


class InitializerDetector:
    id = "SC-INIT-001"
    title = "Unprotected initializer"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            if fn.is_constructor or fn.mutability in {"view", "pure"}:
                continue
            if fn.visibility not in {"public", "external"}:
                continue
            if fn.name.lower().replace("_", "") != "initialize":
                continue
            if function_has_modifier(fn.ast, ACCESS_MODIFIERS | INITIALIZER_MODIFIERS):
                continue
            if has_msg_sender_check(fn.ast):
                continue
            if _has_initialized_guard(fn.ast):
                continue
            findings.append(
                Finding(
                    id=self.id,
                    title=self.title,
                    severity=Severity.HIGH,
                    confidence=88,
                    description=(
                        f"`{fn.name}()` is `{fn.visibility}` with no `initializer` modifier, "
                        f"initialized-flag guard, or caller check. On a proxy, anyone can call "
                        f"it and set owner or implementation parameters."
                    ),
                    location=Location(file=contract.filename, line=fn.line),
                    function=fn.name,
                    recommendation=(
                        "Use OpenZeppelin `Initializable` (`initializer` / `reinitializer`) "
                        "or `require(!initialized); initialized = true` plus access control "
                        "if the call must stay restricted after first use."
                    ),
                    classification="initializer",
                    contract=contract.name,
                )
            )
        return findings
