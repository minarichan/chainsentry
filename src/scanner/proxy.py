"""Resolve a proxy's implementation and fetch that source for analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from scanner.chains import resolve_chain
from scanner.etherscan import (
    SourceNotVerifiedError,
    UnsupportedCompilerError,
    VerifiedContract,
    fetch_verified_source,
)
from scanner.models import ScanResult
from scanner.onchain import (
    read_beacon_implementation,
    read_eip1167_implementation,
    read_eip1967_implementation,
)

ZERO = "0x0000000000000000000000000000000000000000"


def checksum_address(value: str) -> str:
    return Web3.to_checksum_address(value)


def normalize_address(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed or trimmed.lower() in {"0x", ZERO.lower()}:
        return None
    try:
        return checksum_address(trimmed)
    except Exception:
        return None


def resolve_implementation_address(
    verified: VerifiedContract,
    requested: str,
    *,
    rpc_url: Optional[str] = None,
) -> Optional[str]:
    """Explorer implementation, then EIP-1167, EIP-1967 slot, then beacon."""
    requested_cs = checksum_address(requested)
    candidates = [
        normalize_address(verified.implementation),
        read_eip1167_implementation(requested_cs, rpc_url=rpc_url),
        read_eip1967_implementation(requested_cs, rpc_url=rpc_url),
        read_beacon_implementation(requested_cs, rpc_url=rpc_url),
    ]
    for candidate in candidates:
        if candidate and candidate.lower() != requested_cs.lower():
            return candidate
    return None


def _load_implementation(
    requested: str,
    fallback: VerifiedContract,
    impl: str,
    *,
    api_key: Optional[str],
    chain_id: int,
) -> ScanTarget:
    try:
        logic = fetch_verified_source(impl, api_key=api_key, chain_id=chain_id)
    except UnsupportedCompilerError:
        return ScanTarget(
            requested,
            fallback,
            impl,
            "proxy_fallback",
            "Implementation is not Solidity; scanned the proxy instead.",
        )
    except SourceNotVerifiedError:
        return ScanTarget(
            requested,
            fallback,
            impl,
            "proxy_fallback",
            "Implementation is not verified; scanned the proxy instead.",
        )
    except Exception:
        return ScanTarget(
            requested,
            fallback,
            impl,
            "proxy_fallback",
            "Could not fetch implementation source; scanned the proxy instead.",
        )
    return ScanTarget(requested, logic, impl, "implementation")


@dataclass
class ScanTarget:
    requested: str
    analyzed: VerifiedContract
    implementation: Optional[str]
    source_role: str
    note: Optional[str] = None


def fetch_scan_target(
    address: str,
    api_key: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> ScanTarget:
    """Fetch verified source, following a proxy and one extra beacon/clone hop."""
    spec = resolve_chain(chain_id)
    requested = checksum_address(address)
    declared = fetch_verified_source(requested, api_key=api_key, chain_id=spec.id)
    hop = resolve_implementation_address(declared, requested, rpc_url=spec.rpc_url())
    if not hop:
        return ScanTarget(requested, declared, None, "declared")

    target = _load_implementation(
        requested, declared, hop, api_key=api_key, chain_id=spec.id
    )
    if target.source_role != "implementation":
        return target

    extra = resolve_implementation_address(target.analyzed, hop, rpc_url=spec.rpc_url())
    if not extra or extra.lower() in {hop.lower(), requested.lower()}:
        return target

    nested = _load_implementation(
        requested, target.analyzed, extra, api_key=api_key, chain_id=spec.id
    )
    if nested.source_role == "implementation":
        return nested
    return target


def apply_scan_target(result: ScanResult, target: ScanTarget) -> ScanResult:
    result.address = target.requested
    result.implementation_address = target.implementation
    result.analyzed_address = checksum_address(target.analyzed.address)
    result.analyzed_name = target.analyzed.name
    result.source_role = target.source_role
    result.proxy_note = target.note
    return result
