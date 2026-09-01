"""Detect low-level calls whose return value is ignored (SWC-104)."""

from __future__ import annotations

from scanner.ast_utils import call_result_is_used, low_level_call_kind, node_line, walk
from scanner.models import Contract, Finding, Location, Severity


class UncheckedCallsDetector:
    id = "SC-UNCHECKED-001"
    title = "Unchecked External Call"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            for node in walk(fn.ast):
                kind = low_level_call_kind(node)
                if kind not in {"call", "send"}:
                    continue
                if call_result_is_used(node, fn.ast):
                    continue
                findings.append(
                    Finding(
                        id=self.id,
                        title=self.title,
                        severity=Severity.MEDIUM,
                        confidence=88,
                        description=(
                            f"`{fn.name}()` performs a low-level `{kind}` and ignores the returned "
                            f"success flag. The callee may revert or run out of gas without the "
                            f"caller noticing."
                        ),
                        location=Location(
                            file=contract.filename,
                            line=node_line(contract.source, node),
                        ),
                        function=fn.name,
                        recommendation=(
                            "Assign the return value `(bool success, ) = addr.call(...)` and "
                            "`require(success)`, or use `transfer` only when 2300 gas is enough."
                        ),
                        classification="SWC-104",
                        contract=contract.name,
                    )
                )
        return findings
