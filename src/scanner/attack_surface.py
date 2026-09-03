"""Per-function attack-surface analysis."""

from __future__ import annotations

from scanner.ast_utils import (
    assignment_base_name,
    function_has_modifier,
    has_msg_sender_check,
    low_level_call_kind,
    reentrancy_call_kind,
    walk,
)
from scanner.detectors.access_control import function_has_access_control
from scanner.detectors.reentrancy import REENTRANCY_GUARDS
from scanner.models import Contract, Function, FunctionSurface
from scanner.parser import is_analyzable_kind


def _modifies_state(contract: Contract, fn: Function) -> bool:
    if fn.mutability in {"view", "pure"}:
        return False
    storage = contract.state_variable_names
    for node in walk(fn.ast):
        name = assignment_base_name(node)
        if name and name in storage:
            return True
    return fn.mutability in {"nonpayable", "payable"} and fn.visibility in {"public", "external"}


def analyze_function(contract: Contract, fn: Function) -> FunctionSurface:
    kinds: set[str] = set()
    for node in walk(fn.ast):
        kind = reentrancy_call_kind(node) or low_level_call_kind(node)
        if kind:
            kinds.add(kind)

    has_external_call = bool(kinds)
    sends_eth = bool({low_level_call_kind(n) for n in walk(fn.ast)} & {"call", "send", "transfer"})
    has_guard = function_has_modifier(fn.ast, REENTRANCY_GUARDS)
    has_acl = function_has_access_control(fn.ast) or has_msg_sender_check(fn.ast)
    modifies = _modifies_state(contract, fn)
    payable = fn.mutability == "payable"

    notes: list[str] = []
    if fn.visibility in {"public", "external"}:
        notes.append("external/public")
    if payable:
        notes.append("payable")
    if modifies:
        notes.append("modifies state")
    else:
        notes.append("no state modification")
    if has_external_call:
        notes.append("external call")
    else:
        notes.append("no external call")
    if sends_eth:
        notes.append("sends ETH")
    if has_guard:
        notes.append("reentrancy protection")
    elif has_external_call and modifies:
        notes.append("no reentrancy protection")
    if has_acl:
        notes.append("access controlled")

    risk = "LOW"
    if fn.mutability in {"view", "pure"} or fn.visibility in {"internal", "private"}:
        risk = "LOW"
    elif sends_eth and has_external_call and not has_guard:
        risk = "HIGH"
    elif has_external_call and modifies and not has_guard:
        risk = "HIGH"
    elif payable and fn.visibility in {"public", "external"}:
        risk = "MEDIUM"
    elif modifies and fn.visibility in {"public", "external"} and not has_acl:
        risk = "MEDIUM"

    return FunctionSurface(
        name=fn.name,
        contract=contract.name,
        visibility=fn.visibility,
        mutability=fn.mutability,
        payable=payable,
        modifies_state=modifies,
        has_external_call=has_external_call,
        sends_eth=sends_eth,
        has_reentrancy_guard=has_guard,
        has_access_control=has_acl,
        risk=risk,
        notes=notes,
        line=fn.line,
    )


def analyze_contract(contract: Contract) -> list[FunctionSurface]:
    if not is_analyzable_kind(contract.kind):
        return []
    return [analyze_function(contract, fn) for fn in contract.functions]
