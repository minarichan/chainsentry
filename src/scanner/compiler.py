"""Solidity compilation via solc. No security logic lives here."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

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


def parse_pragma(source: str) -> Optional[str]:
    match = PRAGMA_RE.search(source)
    if not match:
        return None
    return match.group(1).strip()


def resolve_solc_version(source: str) -> str:
    """Pick an installable solc version that satisfies a simple pragma."""
    pragma = parse_pragma(source)
    if not pragma:
        return DEFAULT_SOLC

    exact = VERSION_RE.search(pragma.replace(" ", ""))
    pinned = exact.group(1) if exact else None

    if pragma.startswith("=") and pinned:
        return pinned
    if re.fullmatch(r"\d+\.\d+\.\d+", pragma):
        return pragma
    if pinned and pragma.startswith("^0.8"):
        # Stay on the 0.8 line; 0.8.20 is widely available via py-solc-x.
        major_minor = ".".join(pinned.split(".")[:2])
        if major_minor == "0.8":
            return DEFAULT_SOLC
        return pinned
    if pinned:
        return pinned
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


def inject_missing_imports(sources: dict[str, str], remappings: list[str]) -> dict[str, str]:
    """Add well-known interface stubs when Etherscan omitted forge-std / similar libs."""
    filled = dict(sources)
    key_set = {name.replace("\\", "/") for name in filled}
    for content in list(filled.values()):
        for match in IMPORT_RE.finditer(content or ""):
            path = match.group(1).replace("\\", "/")
            if path.startswith(".") or _resolved(path, remappings, key_set):
                continue
            stub = _stub_for(path)
            if stub and path not in filled:
                filled[path] = stub
                key_set.add(path)
    return filled


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
    primary_source = sources[filename]
    flattened = primary_source if len(sources) == 1 else "\n\n".join(
        f"// File: {name}\n{content}" for name, content in sources.items()
    )

    version = solc_version or resolve_solc_version(primary_source)
    try:
        ensure_solc(version)
    except Exception as exc:  # pragma: no cover - environment/network failure
        if solc_version:
            fallback = resolve_solc_version(primary_source)
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

    remaps = infer_remappings(sources, remappings)
    sources = inject_missing_imports(sources, remaps)
    remaps = infer_remappings(sources, remaps)

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
        if use_ir:
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
            return _fail(flattened, filename, version, errors, file_sources=sources)
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
                errors=errors,
                warnings=warnings,
                file_sources=sources,
            )

        file_asts: dict[str, dict[str, Any]] = {}
        for name, data in (output.get("sources") or {}).items():
            file_asts[name] = (data or {}).get("ast") or {}

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
