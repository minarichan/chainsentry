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

    def rpc_urls(self, extra: str | None = None) -> list[str]:
        """Preferred RPC, then public fallbacks. Deduped, order preserved."""
        preferred = (extra or "").strip()
        env = (os.getenv(self.rpc_env) or "").strip()
        extras = RPC_FALLBACKS.get(self.id, ())
        out: list[str] = []
        for url in (preferred, env, self.default_rpc, *extras):
            if url and url not in out:
                out.append(url)
        return out

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
        default_rpc="https://ethereum.publicnode.com",
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

RPC_FALLBACKS: dict[int, tuple[str, ...]] = {
    1: (
        "https://cloudflare-eth.com",
        "https://1rpc.io/eth",
        "https://eth.llamarpc.com",
    ),
    8453: ("https://base.publicnode.com",),
    42161: ("https://arbitrum-one.publicnode.com",),
}


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
