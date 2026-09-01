"""Resolve a proxy's implementation and fetch that source for analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from scanner.etherscan import (
    SourceNotVerifiedError,
    UnsupportedCompilerError,
    VerifiedContract,
    fetch_verified_source,
)
from scanner.models import ScanResult
from scanner.onchain import read_eip1967_implementation

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
    """One hop: Etherscan/Sourcify implementation, else EIP-1967 slot."""
    requested_cs = checksum_address(requested)
    declared = normalize_address(verified.implementation)
    if declared and declared.lower() != requested_cs.lower():
        return declared

    slot = read_eip1967_implementation(requested_cs, rpc_url=rpc_url)
    slot_cs = normalize_address(slot)
    if slot_cs and slot_cs.lower() != requested_cs.lower():
        return slot_cs
    return None


@dataclass
class ScanTarget:
    requested: str
    analyzed: VerifiedContract
    implementation: Optional[str]
    source_role: str
    note: Optional[str] = None


def fetch_scan_target(address: str, api_key: Optional[str] = None) -> ScanTarget:
    """Fetch verified source, following a proxy to its implementation once."""
    requested = checksum_address(address)
    declared = fetch_verified_source(requested, api_key=api_key)
    impl = resolve_implementation_address(declared, requested)
    if not impl:
        return ScanTarget(requested, declared, None, "declared")

    try:
        logic = fetch_verified_source(impl, api_key=api_key)
    except UnsupportedCompilerError as exc:
        return ScanTarget(
            requested,
            declared,
            impl,
            "proxy_fallback",
            f"Implementation {impl} is not Solidity: {exc}",
        )
    except SourceNotVerifiedError as exc:
        return ScanTarget(
            requested,
            declared,
            impl,
            "proxy_fallback",
            f"Implementation {impl} is not verified; scanned proxy source instead. {exc}",
        )
    except Exception as exc:
        return ScanTarget(
            requested,
            declared,
            impl,
            "proxy_fallback",
            f"Could not fetch implementation {impl}: {exc}",
        )

    return ScanTarget(requested, logic, impl, "implementation")


def apply_scan_target(result: ScanResult, target: ScanTarget) -> ScanResult:
    result.address = target.requested
    result.implementation_address = target.implementation
    result.analyzed_address = checksum_address(target.analyzed.address)
    result.analyzed_name = target.analyzed.name
    result.source_role = target.source_role
    result.proxy_note = target.note
    return result
