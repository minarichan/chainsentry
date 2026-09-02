"""On-chain signals: balance, proxy slots, owner, transaction stats."""

from __future__ import annotations

import os
from typing import Optional

from web3 import Web3

from scanner.chains import resolve_chain
from scanner.models import OnChainAnalysis

# EIP-1967 implementation slot
IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

OWNER_ABI = [
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def _web3(rpc_url: Optional[str] = None, chain_id: Optional[int] = None) -> Web3:
    url = (rpc_url or "").strip() or resolve_chain(chain_id).rpc_url()
    return Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 20}))


def read_eip1967_implementation(address: str, rpc_url: Optional[str] = None) -> Optional[str]:
    """Return the EIP-1967 implementation address, if the slot is set."""
    try:
        w3 = _web3(rpc_url)
        return _slot_address(w3, address, IMPLEMENTATION_SLOT)
    except Exception:
        return None


def _slot_address(w3: Web3, address: str, slot: str) -> Optional[str]:
    try:
        value = w3.eth.get_storage_at(Web3.to_checksum_address(address), slot)
        if int.from_bytes(value, "big") == 0:
            return None
        return Web3.to_checksum_address(value[-20:])
    except Exception:
        return None


def _etherscan_tx_stats(
    address: str,
    api_key: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> tuple[Optional[int], Optional[int]]:
    from scanner.etherscan import etherscan_get

    key = api_key or os.getenv("ETHERSCAN_API_KEY") or ""
    if not key:
        return None, None
    try:
        data = etherscan_get(
            {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 10000,
                "sort": "desc",
            },
            api_key=key,
            chain_id=chain_id,
        )
        rows = data.get("result") if data.get("status") == "1" else []
        if not isinstance(rows, list):
            return None, None
        senders = {row.get("from", "").lower() for row in rows if row.get("from")}
        return len(rows), len(senders)
    except Exception:
        return None, None


def analyze_address(
    address: str,
    *,
    rpc_url: Optional[str] = None,
    api_key: Optional[str] = None,
    network: str = "Ethereum Mainnet",
    verified: bool = False,
    chain_id: Optional[int] = None,
) -> OnChainAnalysis:
    w3 = _web3(rpc_url, chain_id)
    checksum = Web3.to_checksum_address(address)
    signals: list[str] = []
    notes: list[str] = []

    balance_wei = 0
    try:
        balance_wei = int(w3.eth.get_balance(checksum))
    except Exception as exc:
        notes.append(f"Could not read balance: {exc}")

    eth_balance = f"{balance_wei / 10**18:.6f} ETH"
    if balance_wei > 10**18:
        signals.append("Large ETH balance")

    implementation = _slot_address(w3, checksum, IMPLEMENTATION_SLOT)
    admin = _slot_address(w3, checksum, ADMIN_SLOT)
    is_proxy = bool(implementation or admin)
    if is_proxy:
        signals.append("Upgradeable proxy")
        if implementation:
            notes.append(f"Implementation: {implementation}")
        if admin:
            notes.append(f"Proxy admin: {admin}")

    owner = None
    try:
        contract = w3.eth.contract(address=checksum, abi=OWNER_ABI)
        owner = contract.functions.owner().call()
        if owner and int(owner, 16) != 0:
            signals.append("Privileged owner")
    except Exception:
        owner = None

    tx_count, unique_users = _etherscan_tx_stats(checksum, api_key, chain_id=chain_id)
    if tx_count is None:
        notes.append("Transaction stats require ETHERSCAN_API_KEY.")

    return OnChainAnalysis(
        address=checksum,
        network=network,
        verified=verified,
        transaction_count=tx_count,
        unique_users=unique_users,
        eth_balance=eth_balance,
        is_proxy=is_proxy,
        implementation=implementation,
        has_privileged_owner=bool(owner),
        owner=owner,
        signals=signals,
        notes=notes,
    )
