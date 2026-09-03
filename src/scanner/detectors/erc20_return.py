"""Flag ignored bool returns from ERC-20 transfer / transferFrom / approve."""

from __future__ import annotations

from scanner.ast_utils import call_result_is_used, high_level_external_call_name, walk
from scanner.models import Contract, Finding, Severity

ERC20_BOOL_METHODS = {"transfer", "transferFrom", "approve"}


class Erc20ReturnDetector:
    id = "SC-ERC20-001"
    title = "Unchecked ERC-20 return"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            for node in walk(fn.ast):
                name = high_level_external_call_name(node)
                if name not in ERC20_BOOL_METHODS:
                    continue
                if call_result_is_used(node, fn.ast):
                    continue
                findings.append(
                    Finding(
                        id=self.id,
                        title=self.title,
                        severity=Severity.MEDIUM,
                        confidence=82,
                        description=(
                            f"`{fn.name}()` calls `{name}` and ignores the returned bool. "
                            f"Some tokens return `false` on failure instead of reverting; the "
                            f"caller can continue as if the transfer succeeded."
                        ),
                        location=contract.location_of(node),
                        function=fn.name,
                        recommendation=(
                            "Use OpenZeppelin `SafeERC20` (`safeTransfer` / `safeTransferFrom` / "
                            "`safeApprove`), or `require(token.transfer(...))`."
                        ),
                        classification="ERC20",
                        contract=contract.name,
                    )
                )
        return findings
