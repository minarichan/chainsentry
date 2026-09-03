"""Turn a solc AST into structured Contract / Function objects."""

from __future__ import annotations

from typing import Any, Optional

from scanner.ast_utils import node_line, type_name
from scanner.compiler import CompilationResult
from scanner.models import Contract, Event, Function, Modifier, Parameter, StateVariable


def _parameters(container: dict[str, Any] | None) -> list[Parameter]:
    if not container:
        return []
    params: list[Parameter] = []
    for item in container.get("parameters") or []:
        params.append(
            Parameter(
                name=item.get("name") or "",
                type=type_name(item.get("typeName")),
            )
        )
    return params


def _inheritance(node: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for spec in node.get("baseContracts") or []:
        base = spec.get("baseName") or {}
        name = base.get("name") or type_name(base)
        if name and name != "unknown":
            names.append(str(name))
    return names


def _parse_function(node: dict[str, Any], source: str) -> Function:
    kind = node.get("kind") or "function"
    name = node.get("name") or kind
    modifiers = []
    for modifier in node.get("modifiers") or []:
        name_node = modifier.get("modifierName") or {}
        modifiers.append(name_node.get("name") or type_name(name_node))
    return Function(
        name=name,
        visibility=node.get("visibility") or "internal",
        mutability=node.get("stateMutability") or "nonpayable",
        parameters=_parameters(node.get("parameters")),
        return_values=_parameters(node.get("returnParameters")),
        modifiers=modifiers,
        is_constructor=kind == "constructor" or node.get("isConstructor") is True,
        is_fallback=kind == "fallback",
        is_receive=kind == "receive",
        line=node_line(source, node),
        src_offset=int(str(node.get("src") or "0").split(":")[0] or 0),
        ast=node,
    )


def _parse_variable(node: dict[str, Any], source: str) -> StateVariable:
    mutability = node.get("mutability") or "mutable"
    return StateVariable(
        name=node.get("name") or "",
        type=type_name(node.get("typeName")),
        visibility=node.get("visibility") or "internal",
        is_constant=bool(node.get("constant")) or mutability == "constant",
        is_immutable=mutability == "immutable",
        line=node_line(source, node),
        ast=node,
    )


def _parse_event(node: dict[str, Any], source: str) -> Event:
    return Event(
        name=node.get("name") or "",
        parameters=_parameters(node.get("parameters")),
        line=node_line(source, node),
    )


def _parse_modifier(node: dict[str, Any], source: str) -> Modifier:
    return Modifier(
        name=node.get("name") or "",
        parameters=_parameters(node.get("parameters")),
        line=node_line(source, node),
        ast=node,
    )


SKIP_KINDS = {"interface", "library"}


def is_analyzable_kind(kind: str | None) -> bool:
    """Interfaces and libraries have no runtime logic we should score."""
    return (kind or "contract") not in SKIP_KINDS


def parse_ast(ast: dict[str, Any], source: str, filename: str, abis: dict[str, list] | None = None) -> list[Contract]:
    contracts: list[Contract] = []
    abis = abis or {}
    for node in ast.get("nodes") or []:
        if node.get("nodeType") != "ContractDefinition":
            continue
        name = node.get("name") or "Unknown"
        kind = node.get("contractKind") or "contract"
        if not is_analyzable_kind(kind):
            continue
        contract = Contract(
            name=name,
            kind=kind,
            filename=filename,
            source=source,
            inheritance=_inheritance(node),
            line=node_line(source, node),
            ast=node,
            abi=abis.get(name) or [],
        )
        for child in node.get("nodes") or []:
            ntype = child.get("nodeType")
            if ntype == "FunctionDefinition":
                contract.functions.append(_parse_function(child, source))
            elif ntype == "VariableDeclaration" and child.get("stateVariable"):
                contract.state_variables.append(_parse_variable(child, source))
            elif ntype == "EventDefinition":
                contract.events.append(_parse_event(child, source))
            elif ntype == "ModifierDefinition":
                contract.modifiers.append(_parse_modifier(child, source))
        contracts.append(contract)
    return contracts


def contract_ast_id(contract: Contract) -> Optional[int]:
    raw = (contract.ast or {}).get("id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def inherited_base_ids(contracts: list[Contract]) -> set[int]:
    """AST ids of contracts that appear as a parent of another parsed contract."""
    bases: set[int] = set()
    for contract in contracts:
        self_id = contract_ast_id(contract)
        for raw in (contract.ast or {}).get("linearizedBaseContracts") or []:
            try:
                bid = int(raw)
            except (TypeError, ValueError):
                continue
            if self_id is None or bid != self_id:
                bases.add(bid)
    by_name = {c.name: c for c in contracts}
    for contract in contracts:
        for parent_name in contract.inheritance:
            parent = by_name.get(parent_name)
            pid = contract_ast_id(parent) if parent else None
            if pid is not None:
                bases.add(pid)
    return bases


def is_inherited_base(contract: Contract, base_ids: set[int]) -> bool:
    cid = contract_ast_id(contract)
    return cid is not None and cid in base_ids


def _bases_to_inherit(contract: Contract, by_id: dict[int, Contract], by_name: dict[str, Contract]) -> list[Contract]:
    self_id = contract_ast_id(contract)
    ordered: list[Contract] = []
    seen: set[int] = set()
    for raw in (contract.ast or {}).get("linearizedBaseContracts") or []:
        try:
            bid = int(raw)
        except (TypeError, ValueError):
            continue
        if self_id is not None and bid == self_id:
            continue
        base = by_id.get(bid)
        if base is None or bid in seen:
            continue
        seen.add(bid)
        ordered.append(base)
    if ordered:
        return ordered
    for parent_name in contract.inheritance:
        parent = by_name.get(parent_name)
        if parent is None:
            continue
        pid = contract_ast_id(parent)
        if pid is not None and pid in seen:
            continue
        if pid is not None:
            seen.add(pid)
        ordered.append(parent)
        for ancestor in _bases_to_inherit(parent, by_id, by_name):
            aid = contract_ast_id(ancestor)
            if aid is not None and aid in seen:
                continue
            if aid is not None:
                seen.add(aid)
            ordered.append(ancestor)
    return ordered


def apply_inheritance(contracts: list[Contract]) -> None:
    """Copy inherited state and non-overridden functions onto most-derived contracts.

    OpenZeppelin / lib contracts are never in `contracts`, so those members stay
    out of analysis. Bases that other parsed contracts inherit are left as-is;
    detectors run only on the leaves so the same body is not reported twice.
    """
    by_id: dict[int, Contract] = {}
    for item in contracts:
        cid = contract_ast_id(item)
        if cid is not None:
            by_id[cid] = item
    by_name = {c.name: c for c in contracts}
    base_ids = inherited_base_ids(contracts)
    for contract in contracts:
        if is_inherited_base(contract, base_ids):
            continue
        seen_fns = {fn.name for fn in contract.functions}
        seen_vars = {var.name for var in contract.state_variables}
        seen_mods = {mod.name for mod in contract.modifiers}
        for base in _bases_to_inherit(contract, by_id, by_name):
            for var in base.state_variables:
                if var.name in seen_vars:
                    continue
                contract.state_variables.append(var)
                seen_vars.add(var.name)
            for fn in base.functions:
                if fn.is_constructor or fn.name in seen_fns:
                    continue
                contract.functions.append(fn)
                seen_fns.add(fn.name)
            for mod in base.modifiers:
                if mod.name in seen_mods:
                    continue
                contract.modifiers.append(mod)
                seen_mods.add(mod.name)


def _is_dependency(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "@openzeppelin" in normalized
        or "node_modules/" in normalized
        or "/lib/" in normalized
        or normalized.startswith("lib/")
    )


def parse_compilation(result: CompilationResult) -> list[Contract]:
    if not result.success:
        return []
    contracts: list[Contract] = []
    if result.file_asts:
        seen: set[tuple] = set()
        for fname, ast in result.file_asts.items():
            if _is_dependency(fname):
                continue
            src = result.file_sources.get(fname, result.source)
            for contract in parse_ast(ast, src, fname, result.abis):
                src_tag = (contract.ast or {}).get("src") or ""
                key = (contract.name, src_tag)
                if key in seen:
                    continue
                seen.add(key)
                contracts.append(contract)
        if not contracts:
            primary_ast = result.file_asts.get(result.filename) or next(iter(result.file_asts.values()), {})
            src = result.file_sources.get(result.filename, result.source)
            contracts = parse_ast(primary_ast, src, result.filename, result.abis)
    else:
        contracts = parse_ast(result.ast, result.source, result.filename, result.abis)
    apply_inheritance(contracts)
    units = _source_units(result)
    for contract in contracts:
        contract.source_units = units
    return contracts


def _source_units(result: CompilationResult) -> dict[int, tuple[str, str]]:
    units: dict[int, tuple[str, str]] = {}
    for index, name in (result.source_ids or {}).items():
        units[int(index)] = (name, result.file_sources.get(name) or result.source)
    if units:
        return units
    for index, (name, src) in enumerate((result.file_sources or {}).items()):
        units[index] = (name, src)
    if not units and result.source:
        units[0] = (result.filename, result.source)
    return units
