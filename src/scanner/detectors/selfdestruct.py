"""Detect selfdestruct / suicide (SWC-106)."""

from __future__ import annotations

from scanner.ast_utils import function_has_modifier, is_selfdestruct_call, node_line, walk
from scanner.detectors.access_control import ACCESS_MODIFIERS
from scanner.models import Contract, Finding, Location, Severity


class SelfdestructDetector:
    id = "SC-SELFDESTRUCT-001"
    title = "Use of selfdestruct"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            for node in walk(fn.ast):
                if not is_selfdestruct_call(node):
                    continue
                protected = function_has_modifier(fn.ast, ACCESS_MODIFIERS)
                findings.append(
                    Finding(
                        id=self.id,
                        title=self.title,
                        severity=Severity.HIGH if not protected else Severity.MEDIUM,
                        confidence=90,
                        description=(
                            f"`{fn.name}()` calls `selfdestruct`, which deletes the contract and "
                            f"sends remaining Ether to a target. "
                            + (
                                "The function is not access-controlled, so anyone may destroy it."
                                if not protected
                                else "Even when gated, destructible contracts surprise integrators and break upgrades."
                            )
                        ),
                        location=Location(
                            file=contract.filename,
                            line=node_line(contract.source, node),
                        ),
                        function=fn.name,
                        recommendation=(
                            "Avoid `selfdestruct`. If funds must be rescued, use a withdrawal "
                            "pattern under strict access control instead of deleting the contract."
                        ),
                        classification="SWC-106",
                        contract=contract.name,
                    )
                )
        return findings
