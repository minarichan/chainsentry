"""Detect authorization that uses tx.origin instead of msg.sender (SWC-115)."""

from __future__ import annotations

from scanner.ast_utils import is_tx_origin, node_line, walk
from scanner.models import Contract, Finding, Location, Severity


class TxOriginDetector:
    id = "SC-TXORIGIN-001"
    title = "Authorization via tx.origin"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            seen_offsets: set[int] = set()
            for node in walk(fn.ast):
                if not is_tx_origin(node):
                    continue
                offset = node_line(contract.source, node)
                if offset in seen_offsets:
                    continue
                seen_offsets.add(offset)
                findings.append(
                    Finding(
                        id=self.id,
                        title=self.title,
                        severity=Severity.HIGH,
                        confidence=95,
                        description=(
                            f"`{fn.name}()` uses `tx.origin` for authorization. `tx.origin` is the "
                            f"original EOA in the call chain, so a malicious contract called by the "
                            f"owner can impersonate them."
                        ),
                        location=Location(file=contract.filename, line=offset),
                        function=fn.name,
                        recommendation="Authorize with `msg.sender` (and/or a dedicated owner variable), never `tx.origin`.",
                        classification="SWC-115",
                        contract=contract.name,
                    )
                )
        return findings
