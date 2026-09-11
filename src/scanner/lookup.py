"""Resolve a scan input: 0x address or ENS name."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from scanner.chains import resolve_chain

_RPC_FAIL_HINTS = (
    "timeout",
    "timed out",
    "connection",
    "server error",
    "bad gateway",
    "cloudflare",
    "429",
    "500",
    "502",
    "503",
    "521",
    "522",
    "524",
    "525",
    "reset",
    "refused",
    "unreachable",
)


def _is_rpc_failure(exc: BaseException) -> bool:
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    return any(hint in text for hint in _RPC_FAIL_HINTS) or "timeout" in name or "http" in name

HEX_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
ENS_NAME_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


class InvalidScanTargetError(ValueError):
    """Input is neither a hex address nor an ENS name."""


class NameNotResolvedError(RuntimeError):
    """ENS lookup returned no address or the resolver failed."""


class NotAContractError(RuntimeError):
    """Address has no runtime bytecode on the selected chain."""


@dataclass(frozen=True)
class ResolvedTarget:
    address: str
    lookup: Optional[str] = None


def _checksum(value: str) -> str:
    return Web3.to_checksum_address(value)


def _ens_address_via(name: str, rpc_url: str) -> Optional[str]:
    from ens import ENS

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
    found = ENS.from_web3(w3).address(name)
    if not found:
        return None
    return _checksum(found)


def resolve_ens_name(name: str, *, rpc_url: Optional[str] = None) -> Optional[str]:
    """Resolve an ENS name on Ethereum mainnet. Returns a checksum address or None."""
    last_error: BaseException | None = None
    for url in resolve_chain(1).rpc_urls(rpc_url):
        try:
            return _ens_address_via(name, url)
        except Exception as exc:
            if not _is_rpc_failure(exc):
                raise
            last_error = exc
    if last_error:
        raise last_error
    return None


def resolve_scan_input(value: str, *, ens_rpc_url: Optional[str] = None) -> ResolvedTarget:
    """Turn a 0x address or ENS name into a checksum address."""
    text = (value or "").strip()
    if not text:
        raise InvalidScanTargetError("Enter a 0x address or an ENS name (example.eth).")

    if HEX_ADDRESS_RE.match(text):
        return ResolvedTarget(_checksum(text))

    if text.lower().startswith("0x"):
        raise InvalidScanTargetError(
            "That is not a valid address. Use a 40-character 0x hash, or an ENS name like example.eth."
        )

    name = text.lower().rstrip(".")
    if not ENS_NAME_RE.match(name):
        raise InvalidScanTargetError("Enter a 0x address or an ENS name (example.eth).")

    try:
        found = resolve_ens_name(name, rpc_url=ens_rpc_url)
    except (InvalidScanTargetError, NameNotResolvedError):
        raise
    except Exception as exc:
        raise NameNotResolvedError(
            f"Could not resolve {name} on ENS. Ethereum RPC did not respond. "
            "Try again, or paste a 0x address."
        ) from exc

    if not found:
        raise NameNotResolvedError(f"ENS has no address for {name}.")
    return ResolvedTarget(found, name)


def describe_target(resolved: ResolvedTarget) -> str:
    if resolved.lookup:
        return f"{resolved.lookup} ({resolved.address})"
    return resolved.address
