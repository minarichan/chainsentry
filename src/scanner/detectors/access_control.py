"""Flag sensitive state-changing functions that lack access control (SWC-105)."""

from __future__ import annotations

from scanner.ast_utils import has_msg_sender_check, is_selfdestruct_call, type_name, walk
from scanner.models import Contract, Finding, Function, Severity

ACCESS_MODIFIERS = {
    "onlyowner",
    "onlyadmin",
    "onlyrole",
    "onlygovernance",
    "onlyminter",
    "onlymanager",
    "onlykeeper",
    "onlyoperator",
    "onlyguardian",
    "onlygov",
    "onlypauser",
    "restricted",
    "auth",
    "authorised",
    "authorized",
    "onlyprivileged",
}

# `onlyInitializing` / `onlyProxy` are OZ lifecycle gates, not caller roles.
_LIFECYCLE_ONLY_MODIFIERS = {
    "onlyinitializing",
    "onlyinitializer",
    "onlyproxy",
    "onlydelegatecall",
    "onlyonce",
    "onlybeacon",
}


def modifier_is_access_control(name: str) -> bool:
    key = name.lower().replace("_", "")
    if not key or key in _LIFECYCLE_ONLY_MODIFIERS:
        return False
    if key in ACCESS_MODIFIERS:
        return True
    if key.startswith("only") and len(key) > 4:
        return True
    return "authorised" in key or "authorized" in key or key.endswith("auth")


def function_has_access_control(fn_ast: dict) -> bool:
    for modifier in fn_ast.get("modifiers") or []:
        name_node = modifier.get("modifierName") or {}
        name = name_node.get("name") or type_name(name_node)
        if modifier_is_access_control(str(name)):
            return True
    return False


# Names that are privileged in typical admin surfaces. `mint` / `burn` are NOT
# here: AMMs and ERC-721 collections expose them publicly on purpose.
SENSITIVE_NAMES = {
    "withdrawall",
    "withdraweth",
    "pause",
    "unpause",
    "destroy",
    "kill",
    "selfdestruct",
    "transferownership",
    "setowner",
    "setadmin",
    "drain",
    "upgrade",
    "upgradeto",
    "upgradetoandcall",
    "changefee",
    "setfee",
    "emergencywithdraw",
    "rug",
}

def _moves_full_balance(fn_ast: dict) -> bool:
    """True when the function reads address(this).balance — typically an admin drain."""
    for node in walk(fn_ast):
        if node.get("nodeType") != "MemberAccess" or node.get("memberName") != "balance":
            continue
        expr = node.get("expression") or {}
        if expr.get("nodeType") == "FunctionCall":
            return True
        if expr.get("name") == "this":
            return True
        type_name = ((expr.get("typeName") or {}).get("name"))
        if type_name == "address":
            return True
    return False


def _has_uint_param(fn: Function) -> bool:
    return any("uint" in (p.type or "").lower() for p in fn.parameters)


def _looks_like_admin_mint(fn: Function) -> bool:
    """Admin mint takes an amount. Pair-style `mint(address to)` does not."""
    name = fn.name.lower().replace("_", "")
    if name not in {"mint", "mintto", "minttokens"} and not name.startswith("mint"):
        return False
    return _has_uint_param(fn)


class AccessControlDetector:
    id = "SC-ACCESS-001"
    title = "Missing Access Control"

    def detect(self, contract: Contract) -> list[Finding]:
        findings: list[Finding] = []
        for fn in contract.functions:
            if fn.is_constructor or fn.is_receive or fn.mutability in {"view", "pure"}:
                continue
            if fn.visibility not in {"public", "external"}:
                continue
            if function_has_access_control(fn.ast):
                continue
            if has_msg_sender_check(fn.ast):
                continue

            name_key = fn.name.lower().replace("_", "")
            sensitive = (
                name_key in SENSITIVE_NAMES
                or _looks_like_admin_mint(fn)
                or _moves_full_balance(fn.ast)
                or any(is_selfdestruct_call(n) for n in walk(fn.ast))
            )
            if not sensitive:
                continue

            findings.append(
                Finding(
                    id=self.id,
                    title=self.title,
                    severity=Severity.HIGH,
                    confidence=85,
                    description=(
                        f"`{fn.name}()` is `{fn.visibility}` and changes privileged state "
                        f"(or moves funds) without an access-control modifier or `msg.sender` check. "
                        f"Any address could call it."
                    ),
                    location=contract.location_of(fn.ast),
                    function=fn.name,
                    recommendation=(
                        "Restrict this function with `onlyOwner` / role-based modifiers, "
                        "or require `msg.sender` to be an authorized account."
                    ),
                    classification="SWC-105",
                    contract=contract.name,
                )
            )
        return findings
