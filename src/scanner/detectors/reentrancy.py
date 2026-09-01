"""Detect external calls that happen before storage is updated (SWC-107)."""

from __future__ import annotations

from scanner.ast_utils import (
    assignment_base_name,
    function_has_modifier,
    node_line,
    node_offset,
    reentrancy_call_kind,
    walk,
)
from scanner.models import Contract, Finding, Location, Severity

REENTRANCY_GUARDS = {
    "nonreentrant",
    "noreentrancy",
    "nonreentrancyguard",
    "lock",
    "nointerrupt",
}


class ReentrancyDetector:
    id = "SC-REENTRANCY-001"
    title = "Potential Reentrancy"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        storage = contract.state_variable_names

        for fn in contract.functions:
            if fn.mutability in {"view", "pure"}:
                continue
            if function_has_modifier(fn.ast, REENTRANCY_GUARDS):
                continue

            calls: list[tuple[int, str, dict]] = []
            writes: list[tuple[int, str, dict]] = []

            for node in walk(fn.ast):
                kind = reentrancy_call_kind(node)
                if kind:
                    calls.append((node_offset(node), kind, node))
                name = assignment_base_name(node)
                if name and name in storage:
                    writes.append((node_offset(node), name, node))

            if not calls or not writes:
                continue

            # Classic CEI violation: an external call occurs before a later storage write.
            for call_off, kind, call_node in calls:
                later_writes = [w for w in writes if w[0] > call_off]
                if not later_writes:
                    continue
                written = ", ".join(sorted({w[1] for w in later_writes}))
                findings.append(
                    Finding(
                        id=self.id,
                        title=self.title,
                        severity=Severity.HIGH,
                        confidence=90 if kind in {"call", "delegatecall"} else 80,
                        description=(
                            f"`{fn.name}()` performs an external `{kind}` before updating "
                            f"storage variable(s) `{written}`. An attacker contract can re-enter "
                            f"before the balance or authorization state is finalized."
                        ),
                        location=Location(
                            file=contract.filename,
                            line=node_line(contract.source, call_node),
                        ),
                        function=fn.name,
                        recommendation=(
                            "Follow Checks-Effects-Interactions: update state before the external "
                            "call, and/or apply a reentrancy guard (`nonReentrant`)."
                        ),
                        classification="SWC-107",
                        contract=contract.name,
                    )
                )
                break
        return findings
