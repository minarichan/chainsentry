"""Turn a solc AST into structured Contract / Function objects."""

from __future__ import annotations

from typing import Any

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
    if result.file_asts:
        contracts: list[Contract] = []
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
        if contracts:
            return contracts
        primary_ast = result.file_asts.get(result.filename) or next(iter(result.file_asts.values()), {})
        src = result.file_sources.get(result.filename, result.source)
        return parse_ast(primary_ast, src, result.filename, result.abis)
    return parse_ast(result.ast, result.source, result.filename, result.abis)
