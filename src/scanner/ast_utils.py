"""Helpers for walking solc AST nodes and mapping source offsets to lines."""

from __future__ import annotations

from typing import Any, Callable, Iterator, Optional


Node = dict[str, Any]
Predicate = Callable[[Node], bool]


def parse_src(src: str | None) -> tuple[int, int, int]:
    """Parse solc `src` field `start:length:index` into integers."""
    if not src:
        return 0, 0, 0
    parts = str(src).split(":")
    try:
        start = int(parts[0])
        length = int(parts[1]) if len(parts) > 1 else 0
        index = int(parts[2]) if len(parts) > 2 else 0
        return start, length, index
    except (TypeError, ValueError):
        return 0, 0, 0


def offset_to_line(source: str, offset: int) -> int:
    if offset <= 0:
        return 1
    if offset >= len(source):
        return source.count("\n") + 1
    return source.count("\n", 0, offset) + 1


def node_offset(node: Node) -> int:
    start, _, _ = parse_src(node.get("src"))
    return start


def node_line(source: str, node: Node) -> int:
    return offset_to_line(source, node_offset(node))


def node_file_and_line(
    node: Node,
    source_units: dict[int, tuple[str, str]],
    default_file: str,
    default_source: str,
) -> tuple[str, int]:
    """Map a solc AST node to (filename, line) using `src` `start:length:index`."""
    start, _, index = parse_src(node.get("src"))
    if index in source_units:
        filename, source = source_units[index]
    elif len(source_units) == 1:
        filename, source = next(iter(source_units.values()))
    else:
        filename, source = default_file, default_source
    return filename, offset_to_line(source, start)


def walk(node: Any) -> Iterator[Node]:
    """Depth-first walk of every dict node in an AST tree."""
    if isinstance(node, dict):
        if "nodeType" in node:
            yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def find_nodes(root: Any, node_type: str) -> list[Node]:
    return [n for n in walk(root) if n.get("nodeType") == node_type]


def find_where(root: Any, predicate: Predicate) -> list[Node]:
    return [n for n in walk(root) if isinstance(n, dict) and predicate(n)]


def type_name(node: Optional[Node]) -> str:
    if not node:
        return "unknown"
    node_type = node.get("nodeType")
    if node.get("name") and node_type in {
        "ElementaryTypeName",
        "UserDefinedTypeName",
        "IdentifierPath",
    }:
        return str(node["name"])
    if node_type == "Mapping":
        key = type_name(node.get("keyType"))
        value = type_name(node.get("valueType"))
        return f"mapping({key} => {value})"
    if node_type == "ArrayTypeName":
        base = type_name(node.get("baseType"))
        length = node.get("length")
        if isinstance(length, dict) and length.get("value"):
            return f"{base}[{length['value']}]"
        return f"{base}[]"
    if "pathNode" in node:
        return type_name(node.get("pathNode"))
    descriptions = node.get("typeDescriptions") or {}
    if descriptions.get("typeString"):
        return str(descriptions["typeString"])
    return node.get("name") or "unknown"


def identifier_name(node: Optional[Node]) -> Optional[str]:
    if not node:
        return None
    if node.get("nodeType") == "Identifier":
        return node.get("name")
    if node.get("nodeType") == "MemberAccess":
        return node.get("memberName")
    return node.get("name")


def is_msg_sender(node: Optional[Node]) -> bool:
    if not node or node.get("nodeType") != "MemberAccess":
        return False
    expr = node.get("expression") or {}
    return node.get("memberName") == "sender" and expr.get("name") == "msg"


def is_tx_origin(node: Optional[Node]) -> bool:
    if not node or node.get("nodeType") != "MemberAccess":
        return False
    expr = node.get("expression") or {}
    return node.get("memberName") == "origin" and expr.get("name") == "tx"


def is_block_member(node: Optional[Node], member: str) -> bool:
    if not node or node.get("nodeType") != "MemberAccess":
        return False
    expr = node.get("expression") or {}
    return node.get("memberName") == member and expr.get("name") == "block"


def unwrap_call_expression(node: Node) -> Node:
    """Walk through FunctionCallOptions (`{value: ...}`) to the callee."""
    current = node
    while current.get("nodeType") == "FunctionCallOptions":
        current = current.get("expression") or {}
    return current


def low_level_call_kind(node: Node) -> Optional[str]:
    """Return call/delegatecall/staticcall/send/transfer if this is a FunctionCall."""
    if node.get("nodeType") != "FunctionCall":
        return None
    expr = unwrap_call_expression(node.get("expression") or {})
    if expr.get("nodeType") != "MemberAccess":
        return None
    member = expr.get("memberName")
    if member not in {"call", "delegatecall", "staticcall", "send", "transfer"}:
        return None
    if member in {"send", "transfer"} and not _is_address_type(_member_base_type(expr)):
        return None
    return member


def _member_base_type(member_access: Node) -> str:
    base = member_access.get("expression") or {}
    return str((base.get("typeDescriptions") or {}).get("typeString") or "")


def _is_address_type(type_string: str) -> bool:
    lowered = type_string.lower().strip()
    return lowered == "address" or lowered.startswith("address ")


def _is_contract_type(type_string: str) -> bool:
    lowered = type_string.lower()
    return "contract " in lowered or lowered.startswith("interface ")


def high_level_external_call_name(node: Node) -> Optional[str]:
    """Return the method name for a call into another contract (e.g. IERC20.transfer)."""
    if node.get("nodeType") != "FunctionCall" or node.get("kind") == "typeConversion":
        return None
    expr = unwrap_call_expression(node.get("expression") or {})
    if expr.get("nodeType") != "MemberAccess":
        return None
    member = expr.get("memberName")
    if not member or member in {"call", "delegatecall", "staticcall", "send"}:
        return None
    base = expr.get("expression") or {}
    if base.get("nodeType") == "Identifier" and base.get("name") == "super":
        return None
    if not _is_contract_type(_member_base_type(expr)):
        return None
    return str(member)


def reentrancy_call_kind(node: Node) -> Optional[str]:
    """External call that can re-enter: low-level value calls or high-level contract methods.

    `staticcall` is excluded (read-only). `address.transfer` / `address.send` are included
    because they still execute the recipient fallback (capped gas, but still CEI-relevant).
    """
    kind = low_level_call_kind(node)
    if kind in {"call", "send", "transfer", "delegatecall"}:
        return kind
    high = high_level_external_call_name(node)
    if high:
        return high
    return None


def is_selfdestruct_call(node: Node) -> bool:
    if node.get("nodeType") != "FunctionCall":
        return False
    expr = node.get("expression") or {}
    return expr.get("nodeType") == "Identifier" and expr.get("name") in {
        "selfdestruct",
        "suicide",
    }


def storage_names_referenced(root: Any, storage: set[str]) -> set[str]:
    """State variable names that appear as identifiers under `root`."""
    found: set[str] = set()
    if not storage:
        return found
    for node in walk(root):
        if node.get("nodeType") != "Identifier":
            continue
        name = node.get("name")
        if name in storage:
            found.add(str(name))
    return found


def assignment_base_name(node: Node) -> Optional[str]:
    """Name of the storage identifier being written, if any."""
    if node.get("nodeType") not in {"Assignment", "UnaryOperation"}:
        return None
    target = node.get("leftHandSide") or node.get("subExpression")
    while target:
        ntype = target.get("nodeType")
        if ntype == "Identifier":
            return target.get("name")
        if ntype == "IndexAccess":
            target = target.get("baseExpression")
            continue
        if ntype == "MemberAccess":
            target = target.get("expression")
            continue
        break
    return None


def function_has_modifier(fn_ast: Node, names: set[str]) -> bool:
    lowered = {n.lower() for n in names}
    for modifier in fn_ast.get("modifiers") or []:
        name_node = modifier.get("modifierName") or {}
        name = name_node.get("name") or type_name(name_node)
        if str(name).lower() in lowered:
            return True
    return False


def _contains_msg_sender(node: Optional[Node]) -> bool:
    if not node:
        return False
    if is_msg_sender(node):
        return True
    return any(is_msg_sender(child) for child in walk(node))


def has_msg_sender_check(root: Any) -> bool:
    """True if the AST compares msg.sender (typical authorization check)."""
    for node in find_nodes(root, "BinaryOperation"):
        if node.get("operator") not in {"==", "!="}:
            continue
        left = node.get("leftExpression") or {}
        right = node.get("rightExpression") or {}
        if _contains_msg_sender(left) or _contains_msg_sender(right):
            return True
    return False


def _contains_node(root: Optional[Node], target: Node) -> bool:
    if not root:
        return False
    if root is target:
        return True
    return any(node is target for node in walk(root))


def call_result_is_used(call_node: Node, fn_ast: Node) -> bool:
    """True if the call is assigned, required, returned, or used as a condition."""
    for node in walk(fn_ast):
        ntype = node.get("nodeType")
        if ntype == "VariableDeclarationStatement" and _contains_node(node.get("initialValue"), call_node):
            return True
        if ntype == "Assignment" and _contains_node(node.get("rightHandSide"), call_node):
            return True
        if ntype == "Return" and _contains_node(node.get("expression"), call_node):
            return True
        if ntype == "IfStatement" and _contains_node(node.get("condition"), call_node):
            return True
        if ntype == "FunctionCall":
            expr = node.get("expression") or {}
            if expr.get("name") in {"require", "assert"}:
                for arg in node.get("arguments") or []:
                    if _contains_node(arg, call_node):
                        return True
    return False


def is_address_this(node: Optional[Node]) -> bool:
    if not node:
        return False
    if node.get("nodeType") == "Identifier" and node.get("name") == "this":
        return True
    if node.get("nodeType") != "FunctionCall":
        return False
    args = node.get("arguments") or []
    if len(args) != 1:
        return False
    arg = args[0]
    return isinstance(arg, dict) and arg.get("nodeType") == "Identifier" and arg.get("name") == "this"


def param_compared_to_msg_sender(fn_ast: Node, param_name: str) -> bool:
    """True if `param == msg.sender` (or !=) appears in the function."""
    for node in find_nodes(fn_ast, "BinaryOperation"):
        if node.get("operator") not in {"==", "!="}:
            continue
        left = node.get("leftExpression") or {}
        right = node.get("rightExpression") or {}
        names = {identifier_name(left), identifier_name(right)}
        if param_name in names and (_contains_msg_sender(left) or _contains_msg_sender(right)):
            return True
    return False


def statements_in_order(body: Optional[Node]) -> list[Node]:
    if not body:
        return []
    statements = body.get("statements") if body.get("nodeType") == "Block" else None
    if not statements:
        return [body] if body.get("nodeType") else []
    ordered: list[Node] = []
    for stmt in statements:
        ordered.append(stmt)
        nested = stmt.get("trueBody") or stmt.get("body") or stmt.get("falseBody")
        if nested:
            ordered.extend(statements_in_order(nested) if nested.get("nodeType") == "Block" else [nested])
        for key in ("trueBody", "falseBody", "body"):
            child = stmt.get(key)
            if child and child is not nested:
                if child.get("nodeType") == "Block":
                    ordered.extend(statements_in_order(child))
                else:
                    ordered.append(child)
    return ordered
