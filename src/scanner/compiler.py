"""Solidity compilation via solc. No security logic lives here."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from solcx import compile_standard, get_installed_solc_versions, install_solc, set_solc_version
from solcx.exceptions import SolcError

PRAGMA_RE = re.compile(r"pragma\s+solidity\s+([^;]+);", re.IGNORECASE)
VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")
IMPORT_RE = re.compile(
    r"""import\s+(?:{[^}]*}\s+from\s+|[\w.\s*,]*\s+from\s+)?["']([^"']+)["']""",
    re.MULTILINE,
)
MISSING_SOURCE_RE = re.compile(r'Source "([^"]+)" not found')

# Default compiler used when a pragma is a range (e.g. ^0.8.0).
DEFAULT_SOLC = "0.8.20"
# py-solc-x cannot install binaries older than this (standard-json era).
MIN_SOLC = (0, 4, 11)
LINE_SOLC = {
    "0.4": "0.4.26",
    "0.5": "0.5.17",
    "0.6": "0.6.12",
    "0.7": "0.7.6",
    "0.8": DEFAULT_SOLC,
}
MAX_ERROR_CHARS = 1600

IERC20_STUB = """\
pragma solidity >=0.6.2;

interface IERC20 {
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}
"""

MISSING_LIB_HINT = (
    "This source imports libraries (often OpenZeppelin) that were not included. "
    "Scan a verified address so explorer sources ship those files, or paste a flattened .sol."
)
MISSING_PROJECT_HINT = (
    "This source imports other files from the same project that were not pasted "
    "(for example src/interface/IProvider.sol). Include those files, paste a flattened .sol, "
    "or scan a verified address so the explorer sends the full source tree."
)
PROJECT_IMPORT_PREFIXES = (
    "src/",
    "lib/",
    "contracts/",
    "interface/",
    "interfaces/",
    "test/",
    "script/",
    "forge-std/",
)
OZ_CONTRACTS = "@openzeppelin/contracts/"
OZ_UPGRADEABLE = "@openzeppelin/contracts-upgradeable/"
OZ_TAGS = ("v5.0.2", "v4.9.6")
OZ_MAX_FILES = 80
OZ_BARE = {
    "TransparentUpgradeableProxy.sol": "proxy/transparent/TransparentUpgradeableProxy.sol",
    "ProxyAdmin.sol": "proxy/transparent/ProxyAdmin.sol",
    "ERC1967Proxy.sol": "proxy/ERC1967/ERC1967Proxy.sol",
    "ERC1967Utils.sol": "proxy/ERC1967/ERC1967Utils.sol",
    "Proxy.sol": "proxy/Proxy.sol",
    "Ownable.sol": "access/Ownable.sol",
    "Ownable2Step.sol": "access/Ownable2Step.sol",
    "ERC20.sol": "token/ERC20/ERC20.sol",
    "IERC20.sol": "token/ERC20/IERC20.sol",
    "Address.sol": "utils/Address.sol",
    "Context.sol": "utils/Context.sol",
    "StorageSlot.sol": "utils/StorageSlot.sol",
    "Initializable.sol": "proxy/utils/Initializable.sol",
    "UUPSUpgradeable.sol": "proxy/utils/UUPSUpgradeable.sol",
    "Clones.sol": "proxy/Clones.sol",
}
OZ_SKIP_FETCH_PREFIX = (
    "lib/",
    "src/",
    "test/",
    "tests/",
    "script/",
    "node_modules/",
    "forge-std/",
    "contracts/",
)
OZ_ROOT_DIRS = {
    "access",
    "finance",
    "governance",
    "interfaces",
    "metatx",
    "proxy",
    "token",
    "utils",
}


@dataclass
class CompilationResult:
    success: bool
    source: str
    filename: str
    solc_version: str
    ast: dict[str, Any] = field(default_factory=dict)
    abis: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    bytecodes: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_asts: dict[str, dict[str, Any]] = field(default_factory=dict)
    file_sources: dict[str, str] = field(default_factory=dict)
    source_ids: dict[int, str] = field(default_factory=dict)


def parse_pragma(source: str) -> Optional[str]:
    match = PRAGMA_RE.search(source)
    if not match:
        return None
    return match.group(1).strip()


def _version_tuple(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.search(version or "")
    if not match:
        return (0, 0, 0)
    parts = match.group(1).split(".")
    return int(parts[0]), int(parts[1]), int(parts[2] if len(parts) > 2 else 0)


def _fmt_version(parsed: tuple[int, int, int]) -> str:
    return f"{parsed[0]}.{parsed[1]}.{parsed[2]}"


def pragma_floor(source: str) -> tuple[int, int, int] | None:
    """Lowest solc the file's pragma will accept (first x.y.z in the pragma)."""
    pragma = parse_pragma(source)
    if not pragma:
        return None
    match = VERSION_RE.search(pragma.replace(" ", ""))
    if not match:
        return None
    return _version_tuple(match.group(1))


def pragma_exact(source: str) -> tuple[int, int, int] | None:
    """Pinned pragma (0.8.17 or =0.8.17). solc rejects any other patch."""
    pragma = (parse_pragma(source) or "").replace(" ", "")
    if re.fullmatch(r"=?\d+\.\d+\.\d+", pragma):
        return _version_tuple(pragma.lstrip("="))
    return None


def solc_for_sources(sources: dict[str, str], requested: str | None = None) -> str:
    """Installable solc that meets every file pragma, not only the primary contract."""
    exacts = [item for item in (pragma_exact(text) for text in sources.values()) if item]
    if exacts:
        pin = min(exacts)
        return usable_solc_version(_fmt_version(pin), "")
    floors = [pragma_floor(text) for text in sources.values()]
    need = max((item for item in floors if item), default=(0, 8, 20))
    req = _version_tuple(requested) if (requested or "").strip() else None
    if req and req >= need:
        return usable_solc_version(_fmt_version(req), "")
    if need[0] == 0 and need[1] == 8 and need < (0, 8, 20):
        need = (0, 8, 20)
    return usable_solc_version(_fmt_version(need), "")


def usable_solc_version(requested: str | None, source: str) -> str:
    """Pick a py-solc-x installable solc. Explorer pins like 0.4.6 cannot be installed."""
    raw = (requested or "").strip() or resolve_solc_version(source)
    parsed = _version_tuple(raw)
    if parsed >= MIN_SOLC:
        return f"{parsed[0]}.{parsed[1]}.{parsed[2]}"
    line = f"{parsed[0]}.{parsed[1]}"
    return LINE_SOLC.get(line, DEFAULT_SOLC)


def resolve_solc_version(source: str) -> str:
    """Pick an installable solc version that satisfies a simple pragma."""
    pragma = parse_pragma(source)
    if not pragma:
        return DEFAULT_SOLC

    exact = VERSION_RE.search(pragma.replace(" ", ""))
    pinned = exact.group(1) if exact else None

    if pragma.startswith("=") and pinned:
        return usable_solc_version(pinned, source)
    if pinned and re.fullmatch(r"\d+\.\d+\.\d+", pragma):
        return usable_solc_version(pinned, source)
    if pinned and pragma.startswith("^0.8"):
        floor = _version_tuple(pinned)
        if floor < (0, 8, 20):
            return DEFAULT_SOLC
        return _fmt_version(floor)
    if pinned and pragma.startswith("^"):
        line = ".".join(pinned.split(".")[:2])
        return LINE_SOLC.get(line, pinned)
    if pinned:
        return usable_solc_version(pinned, source)
    return DEFAULT_SOLC


def ensure_solc(version: str) -> str:
    installed = {str(v) for v in get_installed_solc_versions()}
    if version not in installed:
        install_solc(version)
    set_solc_version(version)
    return version


def _fail(source: str, filename: str, version: str, errors: list[str], **extra: Any) -> CompilationResult:
    return CompilationResult(
        success=False,
        source=source,
        filename=filename,
        solc_version=version,
        errors=errors,
        **extra,
    )


def _split_remap(item: str) -> tuple[str, str]:
    item = item.strip()
    if "=" not in item:
        return "", ""
    left, target = item.split("=", 1)
    prefix = left.split(":", 1)[-1] if ":" in left else left
    return prefix, target


def normalize_remappings(remappings: list[str] | None) -> list[str]:
    """Turn Foundry remappings into solc remappings, including @alias variants."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in remappings or []:
        prefix, target = _split_remap(raw)
        if not prefix:
            continue
        bare = prefix[1:] if prefix.startswith("@") else prefix
        for candidate in (f"{bare}={target}", f"@{bare}={target}"):
            if candidate not in seen:
                seen.add(candidate)
                result.append(candidate)
    return result


def _resolved(import_path: str, remappings: list[str], source_keys: set[str]) -> bool:
    path = import_path.replace("\\", "/")
    if path in source_keys:
        return True
    for item in remappings:
        prefix, target = _split_remap(item)
        if prefix and path.startswith(prefix):
            if (target + path[len(prefix) :]).replace("\\", "/") in source_keys:
                return True
    return False


def _infer_remap(import_path: str, source_keys: list[str]) -> str | None:
    parts = [p for p in import_path.replace("\\", "/").split("/") if p]
    for index in range(1, len(parts)):
        suffix = "/".join(parts[index:])
        prefix = "/".join(parts[:index]) + "/"
        matches = [key for key in source_keys if key.endswith("/" + suffix) or key == suffix]
        if not matches:
            continue
        needle = parts[index - 1].lstrip("@").lower()
        named = [key for key in matches if needle in key.lower()]
        chosen = (named or matches)[0].replace("\\", "/")
        target = chosen[: -len(suffix)]
        return f"{prefix}={target}"
    return None


def infer_remappings(sources: dict[str, str], remappings: list[str] | None = None) -> list[str]:
    remaps = normalize_remappings(remappings)
    keys = [name.replace("\\", "/") for name in sources]
    key_set = set(keys)
    for content in sources.values():
        for match in IMPORT_RE.finditer(content or ""):
            path = match.group(1).replace("\\", "/")
            if path.startswith(".") or _resolved(path, remaps, key_set):
                continue
            inferred = _infer_remap(path, keys)
            if inferred:
                remaps = normalize_remappings(remaps + [inferred])
    return remaps


def _stub_for(import_path: str) -> str | None:
    name = import_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name == "ierc20.sol":
        return IERC20_STUB
    return None


def _join_source(importer: str, imported: str) -> str:
    """Resolve ./ and ../ imports against the importing source-unit name."""
    imported = imported.replace("\\", "/").strip()
    importer = importer.replace("\\", "/")
    if not imported.startswith("."):
        return imported
    parent = importer.rsplit("/", 1)[0] if "/" in importer else ""
    parts = ([p for p in parent.split("/") if p] if parent else []) + imported.split("/")
    out: list[str] = []
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            if out:
                out.pop()
            continue
        out.append(part)
    return "/".join(out)


def inject_missing_imports(sources: dict[str, str], remappings: list[str]) -> dict[str, str]:
    """Add well-known interface stubs when Etherscan omitted forge-std / similar libs."""
    filled = dict(sources)
    key_set = {name.replace("\\", "/") for name in filled}
    for name, content in list(filled.items()):
        importer = name.replace("\\", "/")
        for match in IMPORT_RE.finditer(content or ""):
            raw = match.group(1).replace("\\", "/")
            path = _join_source(_canonical_oz(importer) or importer, raw)
            if _resolved(path, remappings, key_set) or _resolved(raw, remappings, key_set):
                continue
            stub = _stub_for(path) or _stub_for(raw)
            if stub and path not in filled:
                filled[path] = stub
                key_set.add(path)
    return filled


def _unresolved_imports(sources: dict[str, str], remappings: list[str]) -> list[str]:
    key_set = {name.replace("\\", "/") for name in sources}
    missing: list[str] = []
    seen: set[str] = set()
    for name, content in sources.items():
        importer = name.replace("\\", "/")
        for match in IMPORT_RE.finditer(content or ""):
            raw = match.group(1).replace("\\", "/")
            path = _join_source(_canonical_oz(importer) or importer, raw)
            if path in key_set or raw in key_set:
                continue
            if _resolved(path, remappings, key_set) or _resolved(raw, remappings, key_set):
                continue
            if path in seen:
                continue
            seen.add(path)
            missing.append(path)
    return missing


def _oz_repo_and_rel(import_path: str) -> tuple[str, str] | None:
    path = import_path.replace("\\", "/")
    if path.startswith(OZ_CONTRACTS):
        return "openzeppelin-contracts", "contracts/" + path[len(OZ_CONTRACTS) :]
    if path.startswith(OZ_UPGRADEABLE):
        return "openzeppelin-contracts-upgradeable", "contracts/" + path[len(OZ_UPGRADEABLE) :]
    return None


def _canonical_oz(path: str) -> str | None:
    """Map short OZ imports (access/Ownable.sol, ./ProxyAdmin.sol) to @openzeppelin/contracts/…"""
    path = path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    if _oz_repo_and_rel(path):
        return path
    if path in OZ_BARE:
        return OZ_CONTRACTS + OZ_BARE[path]
    lower = path.lower()
    if any(lower.startswith(prefix) for prefix in OZ_SKIP_FETCH_PREFIX):
        return None
    if "/" in path and not path.startswith(".") and ".." not in path.split("/"):
        root = path.split("/", 1)[0]
        if root in OZ_ROOT_DIRS:
            return OZ_CONTRACTS + path
    return None


def _fetch_oz_enabled() -> bool:
    return (os.getenv("SCAN_FETCH_OZ") or "1").strip().lower() not in {"0", "false", "no"}


def _download_oz_file(repo: str, rel: str) -> str | None:
    timeout = httpx.Timeout(20.0)
    for tag in OZ_TAGS:
        url = f"https://raw.githubusercontent.com/OpenZeppelin/{repo}/{tag}/{rel}"
        try:
            response = httpx.get(url, timeout=timeout, follow_redirects=True)
        except httpx.HTTPError:
            continue
        if response.status_code == 200 and response.text.strip():
            return response.text
    return None


def _alias_remaps(aliases: dict[str, set[str]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for canon, als in aliases.items():
        for alias in als:
            if "/" in alias:
                item = f"{alias.rsplit('/', 1)[0]}/={canon.rsplit('/', 1)[0]}/"
            else:
                item = f"{alias}={canon}"
            if item not in seen:
                seen.add(item)
                out.append(item)
    return out


def attach_openzeppelin(sources: dict[str, str], remappings: list[str]) -> tuple[dict[str, str], list[str]]:
    """Pull missing OpenZeppelin files from GitHub, including short import paths."""
    if not _fetch_oz_enabled():
        return sources, []
    filled = dict(sources)
    aliases: dict[str, set[str]] = {}
    pending: list[str] = []
    seen: set[str] = set()

    def queue(raw: str) -> None:
        canon = _canonical_oz(raw)
        if not canon:
            return
        if raw != canon:
            aliases.setdefault(canon, set()).add(raw)
        if canon in seen or canon in filled:
            return
        if canon not in pending:
            pending.append(canon)

    for path in _unresolved_imports(filled, remappings):
        queue(path)

    while pending and len(filled) < len(sources) + OZ_MAX_FILES:
        path = pending.pop(0)
        if path in seen:
            continue
        seen.add(path)
        spec = _oz_repo_and_rel(path)
        if not spec:
            continue
        repo, rel = spec
        body = _download_oz_file(repo, rel)
        if not body:
            continue
        filled[path] = body
        remaps = infer_remappings(filled, remappings + _alias_remaps(aliases))
        for nxt in _unresolved_imports(filled, remaps):
            queue(nxt)
    return filled, _alias_remaps(aliases)


def explain_missing_imports(errors: list[str]) -> list[str]:
    paths = [
        match.group(1)
        for item in errors
        if (match := MISSING_SOURCE_RE.search(item or ""))
    ]
    if not paths:
        return errors
    project = any(path.startswith(PROJECT_IMPORT_PREFIXES) for path in paths)
    hint = MISSING_PROJECT_HINT if project else MISSING_LIB_HINT
    if errors and errors[0] != hint:
        return [hint, *errors]
    return errors


def _shorten(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= MAX_ERROR_CHARS:
        return text
    return text[:MAX_ERROR_CHARS].rstrip() + "\n… (truncated)"


def _extract_issues(output: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for item in output.get("errors") or []:
        text = _shorten(item.get("formattedMessage") or item.get("message") or str(item))
        if item.get("severity") == "warning":
            warnings.append(text)
        else:
            errors.append(text)
    return errors[:12], warnings[:12]


def messages_from_solc_error(exc: SolcError) -> list[str]:
    """Keep the human error (Stack too deep, ParserError, …) and drop solc JSON dumps."""
    payload: Any = None
    if exc.stdout_data:
        try:
            payload = json.loads(exc.stdout_data)
        except json.JSONDecodeError:
            payload = None
    if isinstance(payload, dict):
        errors, _warnings = _extract_issues(payload)
        if errors:
            return errors
    if isinstance(exc.error_dict, dict):
        text = exc.error_dict.get("formattedMessage") or exc.error_dict.get("message")
        if text:
            return [_shorten(str(text))]
    return [_shorten(exc.message or "Compilation failed")]


def _needs_via_ir(errors: list[str]) -> bool:
    return "stack too deep" in "\n".join(errors).lower()


def normalize_optimizer(raw: dict[str, Any] | None) -> dict[str, Any]:
    """solc optimizer settings. Missing values default to off / 200 runs."""
    if not raw or not isinstance(raw, dict):
        return {"enabled": False, "runs": 200}
    enabled = raw.get("enabled")
    if enabled in {True, 1, "1", "true", "True", "yes"}:
        on = True
    elif enabled in {False, 0, "0", "false", "False", "no", None, ""}:
        on = False
    else:
        on = bool(enabled)
    try:
        runs = int(raw.get("runs", 200))
    except (TypeError, ValueError):
        runs = 200
    if runs < 0:
        runs = 200
    return {"enabled": on, "runs": runs}


def _retry_optimizer(opt: dict[str, Any]) -> dict[str, Any]:
    """Keep run count; enable optimizer if stack-too-deep needs viaIR."""
    runs = opt.get("runs", 200)
    try:
        runs = int(runs)
    except (TypeError, ValueError):
        runs = 200
    return {"enabled": True, "runs": runs}


def compile_sources(
    sources: dict[str, str],
    *,
    filename: str | None = None,
    solc_version: str | None = None,
    optimizer: dict[str, Any] | None = None,
    remappings: list[str] | None = None,
    evm_version: str | None = None,
    via_ir: bool = False,
) -> CompilationResult:
    """Compile one or more Solidity files (Etherscan standard-JSON layout)."""
    if not sources:
        return _fail("", filename or "Contract.sol", solc_version or "", ["No source files to compile"])

    filename = filename if filename in sources else next(iter(sources))
    remaps = infer_remappings(sources, remappings)
    sources = inject_missing_imports(sources, remaps)
    remaps = infer_remappings(sources, remaps)
    sources, oz_remaps = attach_openzeppelin(sources, remaps)
    remaps = infer_remappings(sources, remaps + oz_remaps)

    primary_source = sources[filename]
    flattened = primary_source if len(sources) == 1 else "\n\n".join(
        f"// File: {name}\n{content}" for name, content in sources.items()
    )

    version = solc_for_sources(sources, solc_version)
    try:
        ensure_solc(version)
    except Exception as exc:  # pragma: no cover - environment/network failure
        fallback = solc_for_sources(sources, None)
        if fallback != version:
            try:
                ensure_solc(fallback)
                version = fallback
            except Exception:
                return _fail(
                    flattened,
                    filename,
                    version,
                    [f"Failed to install solc {version}: {exc}"],
                    file_sources=sources,
                )
        else:
            return _fail(
                flattened,
                filename,
                version,
                [f"Failed to install solc {version}: {exc}"],
                file_sources=sources,
            )

    def attempt(use_ir: bool, opt: dict[str, Any]) -> CompilationResult:
        settings: dict[str, Any] = {
            "optimizer": opt,
            "outputSelection": {
                "*": {
                    "*": ["abi"],
                    "": ["ast"],
                }
            },
        }
        if remaps:
            settings["remappings"] = remaps
        if evm_version:
            settings["evmVersion"] = evm_version
        # viaIR exists from 0.8.13; older binaries reject the key.
        if use_ir and _version_tuple(version) >= (0, 8, 13):
            settings["viaIR"] = True

        standard_input = {
            "language": "Solidity",
            "sources": {name: {"content": content} for name, content in sources.items()},
            "settings": settings,
        }

        try:
            output = compile_standard(standard_input, solc_version=version)
        except SolcError as exc:
            errors = messages_from_solc_error(exc)
            if not use_ir and _needs_via_ir(errors):
                return attempt(True, _retry_optimizer(opt))
            return _fail(
                flattened, filename, version, explain_missing_imports(errors), file_sources=sources
            )
        except Exception as exc:  # pragma: no cover
            return _fail(
                flattened,
                filename,
                version,
                [f"Compilation failed: {exc}"],
                file_sources=sources,
            )

        errors, warnings = _extract_issues(output)
        if errors:
            if not use_ir and _needs_via_ir(errors):
                return attempt(True, _retry_optimizer(opt))
            return CompilationResult(
                success=False,
                source=flattened,
                filename=filename,
                solc_version=version,
                errors=explain_missing_imports(errors),
                warnings=warnings,
                file_sources=sources,
            )

        file_asts: dict[str, dict[str, Any]] = {}
        source_ids: dict[int, str] = {}
        for name, data in (output.get("sources") or {}).items():
            payload = data or {}
            file_asts[name] = payload.get("ast") or {}
            raw_id = payload.get("id")
            if raw_id is None:
                continue
            try:
                source_ids[int(raw_id)] = name
            except (TypeError, ValueError):
                continue
        if not source_ids:
            for index, name in enumerate(file_asts):
                source_ids[index] = name

        ast = file_asts.get(filename) or next(iter(file_asts.values()), {})
        abis: dict[str, list[dict[str, Any]]] = {}
        bytecodes: dict[str, str] = {}
        for _fname, contracts in (output.get("contracts") or {}).items():
            for name, data in (contracts or {}).items():
                abis[name] = data.get("abi") or []
                bytecodes[name] = ((data.get("evm") or {}).get("bytecode") or {}).get("object") or ""

        return CompilationResult(
            success=True,
            source=flattened,
            filename=filename,
            solc_version=version,
            ast=ast,
            abis=abis,
            bytecodes=bytecodes,
            errors=[],
            warnings=warnings,
            file_asts=file_asts,
            file_sources=sources,
            source_ids=source_ids,
        )

    first_opt = normalize_optimizer(optimizer)
    return attempt(via_ir, first_opt)


def compile_source(source: str, filename: str = "Contract.sol") -> CompilationResult:
    """Compile a single Solidity file and return ABI + AST."""
    return compile_sources({filename: source}, filename=filename)


def compile_file(path: str) -> CompilationResult:
    from pathlib import Path

    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    return compile_source(source, filename=file_path.name)
