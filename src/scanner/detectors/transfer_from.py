"""Flag token.transferFrom(from, ...) where `from` is a caller-controlled parameter."""

from __future__ import annotations

from scanner.ast_utils import (
    high_level_external_call_name,
    identifier_name,
    is_address_this,
    is_msg_sender,
    param_compared_to_msg_sender,
    walk,
)
from scanner.models import Contract, Finding, Severity


class ArbitraryTransferFromDetector:
    id = "SC-TRANSFERFROM-001"
    title = "Arbitrary transferFrom source"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        storage = contract.state_variable_names

        for fn in contract.functions:
            if fn.mutability in {"view", "pure"}:
                continue
            param_names = {p.name for p in fn.parameters if p.name}
            if not param_names:
                continue
            for node in walk(fn.ast):
                if high_level_external_call_name(node) != "transferFrom":
                    continue
                args = node.get("arguments") or []
                if not args:
                    continue
                source = args[0]
                if is_msg_sender(source) or is_address_this(source):
                    continue
                name = identifier_name(source)
                if not name or name not in param_names:
                    continue
                if name in storage:
                    continue
                if param_compared_to_msg_sender(fn.ast, name):
                    continue
                findings.append(
                    Finding(
                        id=self.id,
                        title=self.title,
                        severity=Severity.HIGH,
                        confidence=84,
                        description=(
                            f"`{fn.name}()` calls `transferFrom` with `{name}` taken from a "
                            f"function argument. Anyone who has approved this contract can be "
                            f"drained if a caller passes their address as `{name}`."
                        ),
                        location=contract.location_of(node),
                        function=fn.name,
                        recommendation=(
                            "Pull tokens from `msg.sender` (`transferFrom(msg.sender, ...)`), "
                            "or `require(from == msg.sender)` before the transfer."
                        ),
                        classification="arbitrary-from",
                        contract=contract.name,
                    )
                )
        return findings
