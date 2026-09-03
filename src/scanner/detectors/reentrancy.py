"""Detect external calls that happen before storage is updated (SWC-107)."""

from __future__ import annotations

from scanner.ast_utils import (
    assignment_base_name,
    function_has_modifier,
    node_offset,
    reentrancy_call_kind,
    walk,
)
from scanner.detectors.access_control import function_has_access_control
from scanner.detectors.initializer import INITIALIZER_MODIFIERS
from scanner.models import Contract, Finding, Function, Severity

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
                        location=contract.location_of(call_node),
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


def _externally_callable(fn: Function) -> bool:
    if fn.is_constructor or fn.mutability in {"view", "pure"}:
        return False
    if fn.is_fallback or fn.is_receive:
        return True
    return fn.visibility in {"public", "external"}


def _mutable_storage(contract: Contract) -> set[str]:
    return {
        var.name
        for var in contract.state_variables
        if var.name and not var.is_constant and not var.is_immutable
    }


_SETUP_FNS = {"initialize", "init", "reinitialize"}
_CIRCUIT_BREAKER_FNS = {"pause", "unpause"}


def _calls_and_writes(
    fn: Function, storage: set[str]
) -> tuple[list[tuple[int, str, dict]], list[tuple[int, str, dict]]]:
    calls: list[tuple[int, str, dict]] = []
    writes: list[tuple[int, str, dict]] = []
    for node in walk(fn.ast):
        kind = reentrancy_call_kind(node)
        if kind:
            calls.append((node_offset(node), kind, node))
        name = assignment_base_name(node)
        if name and name in storage:
            writes.append((node_offset(node), name, node))
    return calls, writes


def _is_getter_kind(kind: str) -> bool:
    """View-style method names; a reentrant attacker does not enter through these."""
    if kind in {"call", "delegatecall", "send", "transfer"}:
        return False
    name = kind.replace("_", "")
    lowered = name.lower()
    if lowered in {"balanceof", "allowance", "ownerof", "totalsupply", "code", "supportsinterface"}:
        return True
    for prefix in ("get", "has", "is"):
        if name.startswith(prefix) and (len(name) == len(prefix) or name[len(prefix)].isupper()):
            return True
    return False


def _setup_or_admin_fn(fn: Function) -> bool:
    key = fn.name.lower().replace("_", "")
    if key in _SETUP_FNS or key.startswith("initialize"):
        return True
    if key in _CIRCUIT_BREAKER_FNS:
        return True
    if function_has_access_control(fn.ast):
        return True
    if function_has_modifier(fn.ast, INITIALIZER_MODIFIERS):
        return True
    return False


def _storage_read_before(fn: Function, storage: set[str], call_off: int, call_node: dict) -> set[str]:
    """State reads that happen before `call_node`, excluding the callee expression itself."""
    inside_call = {id(node) for node in walk(call_node)}
    found: set[str] = set()
    for node in walk(fn.ast):
        if node.get("nodeType") != "Identifier":
            continue
        if id(node) in inside_call or node_offset(node) >= call_off:
            continue
        name = node.get("name")
        if name in storage:
            found.add(str(name))
    return found


class CrossFunctionReentrancyDetector:
    """SWC-107 when the write lives in a sibling function, not after the same call.

    Same-function CEI stays on SC-REENTRANCY-001. This flags an unguarded external
    call while storage it already read is still stale, and another public function
    can write that storage (the second entry point during the call).
    """

    id = "SC-REENTRANCY-002"
    title = "Cross-function reentrancy"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        storage = _mutable_storage(contract)
        if not storage:
            return findings

        callable_fns = [fn for fn in contract.functions if _externally_callable(fn)]

        for fn in callable_fns:
            calls, writes = _calls_and_writes(fn, storage)
            reenter_calls = [item for item in calls if not _is_getter_kind(item[1])]
            if not reenter_calls:
                continue
            if any(write_off > call_off for call_off, _, _ in calls for write_off, _, _ in writes):
                continue

            call_off, kind, call_node = min(reenter_calls, key=lambda item: item[0])
            written_before = {name for off, name, _ in writes if off < call_off}
            stale = _storage_read_before(fn, storage, call_off, call_node) - written_before
            if not stale:
                continue

            siblings: list[tuple[str, set[str]]] = []
            fn_guarded = function_has_modifier(fn.ast, REENTRANCY_GUARDS)
            for other in callable_fns:
                if other is fn or other.name == fn.name:
                    continue
                if _setup_or_admin_fn(other):
                    continue
                if fn_guarded and function_has_modifier(other.ast, REENTRANCY_GUARDS):
                    continue
                other_writes: set[str] = set()
                for node in walk(other.ast):
                    name = assignment_base_name(node)
                    if name and name in stale:
                        other_writes.add(name)
                if other_writes:
                    siblings.append((other.name, other_writes))

            if not siblings:
                continue

            sibling_names = ", ".join(f"`{name}()`" for name, _ in sorted(siblings))
            written = ", ".join(
                sorted({var for _, vars_written in siblings for var in vars_written})
            )
            findings.append(
                Finding(
                    id=self.id,
                    title=self.title,
                    severity=Severity.HIGH,
                    confidence=70 if kind in {"call", "delegatecall"} else 65,
                    description=(
                        f"`{fn.name}()` performs an external `{kind}` while storage "
                        f"`{written}` is still stale. {sibling_names} write(s) that "
                        "state and can run in the same transaction before it is finalized."
                    ),
                    location=contract.location_of(call_node),
                    function=fn.name,
                    recommendation=(
                        "Update the shared state before the external call, and apply the "
                        "same reentrancy guard (`nonReentrant`) on every function that "
                        "reads or writes that state."
                    ),
                    classification="SWC-107",
                    contract=contract.name,
                )
            )
        return findings
