"""Detect selfdestruct / suicide (SWC-106)."""

from __future__ import annotations

from scanner.ast_utils import is_selfdestruct_call, walk
from scanner.detectors.access_control import function_has_access_control
from scanner.models import Contract, Finding, Severity


class SelfdestructDetector:
    id = "SC-SELFDESTRUCT-001"
    title = "Use of selfdestruct"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            for node in walk(fn.ast):
                if not is_selfdestruct_call(node):
                    continue
                protected = function_has_access_control(fn.ast)
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
                        location=contract.location_of(node),
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
