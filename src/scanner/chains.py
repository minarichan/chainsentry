"""Supported EVM chains for verified-source lookup and RPC."""

from __future__ import annotations

import os
from dataclasses import dataclass


class UnsupportedChainError(ValueError):
    pass


@dataclass(frozen=True)
class ChainSpec:
    id: int
    label: str
    network: str
    rpc_env: str
    default_rpc: str
    blockscout_base: str

    def rpc_url(self) -> str:
        return (os.getenv(self.rpc_env) or "").strip() or self.default_rpc

    def blockscout_contract_url(self, address: str) -> str:
        if self.id == 1:
            custom = (os.getenv("BLOCKSCOUT_API_URL") or "").strip().rstrip("/")
            if custom:
                return f"{custom}/{address}"
        return f"{self.blockscout_base.rstrip('/')}/{address}"


CHAINS: dict[int, ChainSpec] = {
    1: ChainSpec(
        id=1,
        label="Ethereum",
        network="Ethereum Mainnet",
        rpc_env="ETH_RPC_URL",
        default_rpc="https://eth.llamarpc.com",
        blockscout_base="https://eth.blockscout.com/api/v2/smart-contracts",
    ),
    8453: ChainSpec(
        id=8453,
        label="Base",
        network="Base",
        rpc_env="BASE_RPC_URL",
        default_rpc="https://mainnet.base.org",
        blockscout_base="https://base.blockscout.com/api/v2/smart-contracts",
    ),
    42161: ChainSpec(
        id=42161,
        label="Arbitrum One",
        network="Arbitrum One",
        rpc_env="ARB_RPC_URL",
        default_rpc="https://arb1.arbitrum.io/rpc",
        blockscout_base="https://arbitrum.blockscout.com/api/v2/smart-contracts",
    ),
}

SUPPORTED_CHAIN_IDS = tuple(CHAINS)


def default_chain_id() -> int:
    try:
        value = int(os.getenv("ETHERSCAN_CHAIN_ID", "1"))
    except ValueError:
        return 1
    return value if value in CHAINS else 1


def resolve_chain(chain_id: int | None = None) -> ChainSpec:
    cid = default_chain_id() if chain_id is None else int(chain_id)
    spec = CHAINS.get(cid)
    if spec is None:
        raise UnsupportedChainError(
            "Unsupported chain_id. Use 1 (Ethereum), 8453 (Base), or 42161 (Arbitrum)."
        )
    return spec
