"""Etherscan verified-source retrieval (API V2)."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from scanner import settings as _settings  # noqa: F401  loads .env
from scanner.chains import resolve_chain

ETHERSCAN_V2_URL = os.getenv("ETHERSCAN_API_URL", "https://api.etherscan.io/v2/api")
VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")


class SourceNotVerifiedError(RuntimeError):
    pass


class UnsupportedCompilerError(RuntimeError):
    pass


class EtherscanBudgetError(RuntimeError):
    pass


@dataclass
class VerifiedContract:
    address: str
    name: str
    source: str
    compiler_version: str
    solc_version: str
    verified: bool
    sources: dict[str, str] = field(default_factory=dict)
    primary_file: str = "Contract.sol"
    optimizer: dict[str, Any] | None = None
    remappings: list[str] = field(default_factory=list)
    evm_version: str | None = None
    via_ir: bool = False
    is_proxy: bool = False
    implementation: Optional[str] = None
    extra: dict = field(default_factory=dict)


def parse_solc_version(raw: str) -> Optional[str]:
    """Turn Etherscan `CompilerVersion` (`v0.8.20+commit...`) into `0.8.20`."""
    if not raw or raw.lower().startswith("vyper"):
        return None
    match = VERSION_RE.search(raw)
    return match.group(1) if match else None


def _unwrap_source(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("{{") and raw.endswith("}}"):
        return raw[1:-1]
    return raw


def parse_source_files(
    raw: str, contract_name: str
) -> tuple[dict[str, str], str, dict[str, Any] | None, list[str], str | None]:
    """Return (path → content, primary path, optimizer settings, remappings, evm version)."""
    raw = _unwrap_source(raw)
    primary = f"{contract_name or 'Contract'}.sol"
    empty: list[str] = []
    if not raw:
        return {}, primary, None, empty, None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {primary: raw}, primary, None, empty, None

    if not isinstance(payload, dict):
        return {primary: raw}, primary, None, empty, None

    optimizer = None
    remappings: list[str] = []
    evm_version = None
    settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else None
    if settings and isinstance(settings.get("optimizer"), dict):
        optimizer = settings["optimizer"]
    if settings and isinstance(settings.get("remappings"), list):
        remappings = [str(item) for item in settings["remappings"]]
    if settings:
        evm = settings.get("evmVersion")
        if evm not in {None, "", "Default", "default"}:
            evm_version = str(evm)

    sources_blob = payload.get("sources") if isinstance(payload.get("sources"), dict) else None
    if sources_blob is None and payload and all(isinstance(v, dict) and "content" in v for v in payload.values()):
        sources_blob = payload

    if not sources_blob:
        return {primary: raw}, primary, optimizer, remappings, evm_version

    files: dict[str, str] = {}
    for name, body in sources_blob.items():
        content = body.get("content") if isinstance(body, dict) else str(body)
        files[str(name)] = content or ""

    for path in files:
        if path.endswith(f"{contract_name}.sol") or path.replace("\\", "/").endswith(f"/{contract_name}.sol"):
            primary = path
            break
    else:
        primary = next(iter(files))

    return files, primary, optimizer, remappings, evm_version


def _flatten(files: dict[str, str]) -> str:
    if not files:
        return ""
    if len(files) == 1:
        return next(iter(files.values()))
    return "\n\n".join(f"// File: {name}\n{content}" for name, content in files.items())


def _api_key(explicit: Optional[str] = None) -> str:
    return (explicit or os.getenv("ETHERSCAN_API_KEY") or "").strip()


_budget_lock = threading.Lock()
_budget_hits: list[float] = []


def reset_etherscan_budget_for_tests() -> None:
    global _budget_hits
    with _budget_lock:
        _budget_hits = []


def _consume_etherscan_budget() -> None:
    raw = (os.getenv("ETHERSCAN_MAX_PER_HOUR") or "40").strip()
    try:
        cap = int(raw)
    except ValueError:
        cap = 40
    if cap <= 0:
        return
    now = time.monotonic()
    global _budget_hits
    with _budget_lock:
        _budget_hits = [stamp for stamp in _budget_hits if now - stamp < 3600]
        if len(_budget_hits) >= cap:
            raise EtherscanBudgetError("Etherscan hourly cap reached; trying other explorers.")
        _budget_hits.append(now)


def etherscan_get(
    params: dict[str, Any],
    api_key: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> dict[str, Any]:
    key = _api_key(api_key)
    if not key:
        raise RuntimeError(
            "Missing ETHERSCAN_API_KEY. Copy .env.example to .env and add a free key from https://etherscan.io/apis"
        )
    _consume_etherscan_budget()
    query = {"chainid": resolve_chain(chain_id).id, "apikey": key, **params}
    with httpx.Client(timeout=30.0) as client:
        response = client.get(ETHERSCAN_V2_URL, params=query)
        response.raise_for_status()
        return response.json()


def _from_etherscan_row(address: str, row: dict[str, Any]) -> VerifiedContract:
    source_raw = row.get("SourceCode") or ""
    name = row.get("ContractName") or "Unknown"
    if not source_raw or source_raw in {"", "0"}:
        raise SourceNotVerifiedError("Not verified on Etherscan.")

    compiler_raw = row.get("CompilerVersion") or ""
    if compiler_raw.lower().startswith("vyper"):
        raise UnsupportedCompilerError("This contract is Vyper. ChainSentry only analyzes Solidity.")

    files, primary, optimizer, remappings, evm_version = parse_source_files(source_raw, name)
    solc_version = parse_solc_version(compiler_raw) or ""

    if row.get("OptimizationUsed") in {"1", 1, True} and optimizer is None:
        try:
            runs = int(row.get("Runs") or 200)
        except (TypeError, ValueError):
            runs = 200
        optimizer = {"enabled": True, "runs": runs}

    if not evm_version:
        raw_evm = row.get("EVMVersion")
        if raw_evm not in {None, "", "Default", "default"}:
            evm_version = str(raw_evm)

    via_ir = False
    try:
        parsed = json.loads(_unwrap_source(source_raw))
        if isinstance(parsed, dict):
            via_ir = bool((parsed.get("settings") or {}).get("viaIR"))
    except json.JSONDecodeError:
        via_ir = False

    return VerifiedContract(
        address=address,
        name=name,
        source=_flatten(files),
        compiler_version=compiler_raw,
        solc_version=solc_version,
        verified=True,
        sources=files,
        primary_file=primary,
        optimizer=optimizer,
        remappings=remappings,
        evm_version=evm_version,
        via_ir=via_ir,
        is_proxy=str(row.get("Proxy") or "0") == "1",
        implementation=row.get("Implementation") or None,
        extra=row,
    )


def fetch_from_etherscan(
    address: str,
    api_key: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> VerifiedContract:
    data = etherscan_get(
        {"module": "contract", "action": "getsourcecode", "address": address},
        api_key=api_key,
        chain_id=chain_id,
    )
    if data.get("status") != "1" or not data.get("result"):
        message = data.get("result") or data.get("message") or "Unknown Etherscan error"
        raise RuntimeError(f"Etherscan lookup failed: {message}")

    result = data["result"]
    row = result[0] if isinstance(result, list) else result
    if not isinstance(row, dict):
        raise RuntimeError(f"Etherscan lookup failed: {result}")
    return _from_etherscan_row(address, row)


def fetch_from_sourcify(address: str, chain_id: Optional[int] = None) -> VerifiedContract:
    chain = resolve_chain(chain_id).id
    url = f"https://sourcify.dev/server/v2/contract/{chain}/{address}"
    params = {"fields": "compilation,stdJsonInput,proxyResolution"}
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=params)
        if response.status_code == 404:
            raise SourceNotVerifiedError("Not verified on Sourcify.")
        response.raise_for_status()
        payload = response.json()

    compilation = payload.get("compilation") if isinstance(payload.get("compilation"), dict) else {}
    language = str(compilation.get("language") or "")
    compiler_raw = str(compilation.get("compilerVersion") or "")
    if language.lower() == "vyper" or compiler_raw.lower().startswith("vyper"):
        raise UnsupportedCompilerError("This contract is Vyper. ChainSentry only analyzes Solidity.")

    std = payload.get("stdJsonInput") if isinstance(payload.get("stdJsonInput"), dict) else {}
    sources_blob = std.get("sources") if isinstance(std.get("sources"), dict) else {}
    files: dict[str, str] = {}
    for name, body in sources_blob.items():
        content = body.get("content") if isinstance(body, dict) else str(body)
        if content:
            files[str(name)] = content
    if not files:
        raise SourceNotVerifiedError("Sourcify listed the contract but returned no Solidity source.")

    settings = compilation.get("compilerSettings") if isinstance(compilation.get("compilerSettings"), dict) else {}
    if not settings and isinstance(std.get("settings"), dict):
        settings = std["settings"]
    optimizer = settings.get("optimizer") if isinstance(settings.get("optimizer"), dict) else None
    remappings = [str(item) for item in settings.get("remappings") or []]
    evm_version = settings.get("evmVersion") if settings.get("evmVersion") not in {None, "", "Default", "default"} else None
    via_ir = bool(settings.get("viaIR"))

    qualified = str(compilation.get("fullyQualifiedName") or "")
    primary = qualified.split(":")[0] if ":" in qualified else (next(iter(files)))
    if primary not in files:
        primary = next(iter(files))
    name = str(compilation.get("name") or Path(primary).stem)
    proxy = payload.get("proxyResolution") if isinstance(payload.get("proxyResolution"), dict) else {}
    implementations = proxy.get("implementations") if isinstance(proxy.get("implementations"), list) else []
    implementation = None
    if implementations and isinstance(implementations[0], dict):
        implementation = implementations[0].get("address")

    return VerifiedContract(
        address=address,
        name=name,
        source=_flatten(files),
        compiler_version=compiler_raw,
        solc_version=parse_solc_version(compiler_raw) or "",
        verified=True,
        sources=files,
        primary_file=primary,
        optimizer=optimizer,
        remappings=remappings,
        evm_version=evm_version,
        via_ir=via_ir,
        is_proxy=bool(proxy.get("isProxy")),
        implementation=implementation,
        extra={"source": "sourcify", "evmVersion": evm_version, "payload": {"match": payload.get("match")}},
    )


def _blockscout_contract_url(address: str, chain_id: Optional[int] = None) -> str:
    return resolve_chain(chain_id).blockscout_contract_url(address)


def _from_blockscout_payload(address: str, payload: dict[str, Any]) -> VerifiedContract:
    source = payload.get("source_code") or ""
    if not payload.get("is_verified") and not source:
        raise SourceNotVerifiedError("Not verified on Blockscout.")
    if not source:
        raise SourceNotVerifiedError("Blockscout marked it verified but returned no source.")

    compiler_raw = str(payload.get("compiler_version") or "")
    if str(payload.get("language") or "").lower() == "vyper" or compiler_raw.lower().startswith("vyper"):
        raise UnsupportedCompilerError("This contract is Vyper. ChainSentry only analyzes Solidity.")

    name = str(payload.get("name") or "Contract")
    primary = str(payload.get("file_path") or f"{name}.sol")
    files: dict[str, str] = {primary: source}
    for extra in payload.get("additional_sources") or []:
        if not isinstance(extra, dict):
            continue
        path = str(extra.get("file_path") or extra.get("fileName") or "")
        content = extra.get("source_code") or extra.get("sourceCode") or ""
        if path and content:
            files[path] = str(content)

    settings = payload.get("compiler_settings") if isinstance(payload.get("compiler_settings"), dict) else {}
    optimizer = settings.get("optimizer") if isinstance(settings.get("optimizer"), dict) else None
    if optimizer is None and payload.get("optimization_enabled") in {True, 1, "1"}:
        try:
            runs = int(payload.get("optimization_runs") or 200)
        except (TypeError, ValueError):
            runs = 200
        optimizer = {"enabled": True, "runs": runs}
    remappings = [str(item) for item in (settings.get("remappings") or [])]
    evm_version = settings.get("evmVersion") or payload.get("evm_version")
    if evm_version in {None, "", "Default", "default"}:
        evm_version = None
    via_ir = bool(settings.get("viaIR"))
    implementations = payload.get("implementations") if isinstance(payload.get("implementations"), list) else []
    implementation = None
    if implementations and isinstance(implementations[0], dict):
        implementation = implementations[0].get("address") or implementations[0].get("address_hash")

    return VerifiedContract(
        address=address,
        name=name,
        source=_flatten(files),
        compiler_version=compiler_raw,
        solc_version=parse_solc_version(compiler_raw) or "",
        verified=True,
        sources=files,
        primary_file=primary if primary in files else next(iter(files)),
        optimizer=optimizer,
        remappings=remappings,
        evm_version=str(evm_version) if evm_version else None,
        via_ir=via_ir,
        is_proxy=bool(payload.get("proxy_type")),
        implementation=implementation,
        extra={"source": "blockscout", "payload": {"name": name}},
    )


def fetch_from_blockscout(address: str, chain_id: Optional[int] = None) -> VerifiedContract:
    url = _blockscout_contract_url(address, chain_id=chain_id)
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        if response.status_code == 404:
            raise SourceNotVerifiedError("Not verified on Blockscout.")
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Blockscout returned an unexpected payload.")
    return _from_blockscout_payload(address, payload)


def _short_exc(exc: BaseException) -> str:
    text = str(exc).strip().splitlines()[0]
    return text[:100]


def fetch_verified_source(
    address: str,
    api_key: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> VerifiedContract:
    """Fetch verified Solidity: Sourcify, then Etherscan V2 (API key), then Blockscout."""
    from scanner.settings import load_environment

    load_environment()
    spec = resolve_chain(chain_id)
    key = _api_key(api_key)
    missed: list[str] = []
    errors: list[str] = []

    try:
        return fetch_from_sourcify(address, chain_id=spec.id)
    except UnsupportedCompilerError:
        raise
    except SourceNotVerifiedError:
        missed.append("Sourcify")
    except Exception as exc:
        errors.append(f"Sourcify failed ({_short_exc(exc)})")

    if key:
        try:
            return fetch_from_etherscan(address, api_key=key, chain_id=spec.id)
        except UnsupportedCompilerError:
            raise
        except SourceNotVerifiedError:
            missed.append("Etherscan")
        except EtherscanBudgetError as exc:
            errors.append(_short_exc(exc))
        except Exception as exc:
            errors.append(f"Etherscan failed ({_short_exc(exc)})")

    try:
        return fetch_from_blockscout(address, chain_id=spec.id)
    except UnsupportedCompilerError:
        raise
    except SourceNotVerifiedError:
        missed.append("Blockscout")
    except Exception as exc:
        errors.append(f"Blockscout failed ({_short_exc(exc)})")

    names = ", ".join(missed) if missed else "explorers"
    message = f"No verified Solidity source on {names} for this chain."
    if not key:
        message += (
            " This demo uses Sourcify, then Blockscout; it has no Etherscan key, "
            "so explorer-only contracts will miss. Try the example address, or paste a .sol file. "
            "Locally you can add ETHERSCAN_API_KEY to .env to also try Etherscan."
        )
    else:
        message += " The contract is not verified on those explorers."
    if errors:
        message += " " + " ".join(errors)
    raise SourceNotVerifiedError(message)
