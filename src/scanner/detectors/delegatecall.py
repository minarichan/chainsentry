"""Detect delegatecall, especially to a caller-controlled target (SWC-112)."""

from __future__ import annotations

from scanner.ast_utils import identifier_name, low_level_call_kind, node_line, unwrap_call_expression, walk
from scanner.models import Contract, Finding, Location, Severity


def _delegate_target_name(call_node: dict) -> str | None:
    expr = unwrap_call_expression(call_node.get("expression") or {})
    base = expr.get("expression") if expr.get("nodeType") == "MemberAccess" else None
    return identifier_name(base)


class DelegateCallDetector:
    id = "SC-DELEGATECALL-001"
    title = "Dangerous Delegatecall"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            param_names = {p.name for p in fn.parameters if p.name}
            for node in walk(fn.ast):
                if low_level_call_kind(node) != "delegatecall":
                    continue
                target = _delegate_target_name(node)
                user_controlled = bool(target and target in param_names)
                confidence = 92 if user_controlled else 70
                severity = Severity.HIGH if user_controlled else Severity.MEDIUM
                extra = (
                    f" The target `{target}` is a function parameter, so a caller can execute "
                    f"arbitrary code in this contract's storage context."
                    if user_controlled
                    else " Confirm the callee is a trusted, immutable implementation."
                )
                findings.append(
                    Finding(
                        id=self.id,
                        title=self.title,
                        severity=severity,
                        confidence=confidence,
                        description=(
                            f"`{fn.name}()` uses `delegatecall`. Delegatecall runs the callee's code "
                            f"with the caller's storage, `msg.sender`, and `msg.value`.{extra}"
                        ),
                        location=Location(
                            file=contract.filename,
                            line=node_line(contract.source, node),
                        ),
                        function=fn.name,
                        recommendation=(
                            "Never `delegatecall` to a user-supplied address. Use a fixed "
                            "implementation (proxy pattern) and restrict who can upgrade it."
                        ),
                        classification="SWC-112",
                        contract=contract.name,
                    )
                )
        return findings
