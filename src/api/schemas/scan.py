from typing import Literal

from pydantic import BaseModel, Field, field_validator

from scanner.models import Finding, ScanResult
from scanner.scoring import compute_score


class ScanRequest(BaseModel):
    source: str | None = Field(default=None, description="Solidity source code")
    filename: str = "Contract.sol"
    address: str | None = Field(default=None, description="Verified contract address")
    include_onchain: bool = True
    chain_id: Literal[1, 8453, 42161] = Field(
        default=1,
        description="EVM chain: 1 Ethereum, 8453 Base, 42161 Arbitrum One",
    )
    etherscan_api_key: str | None = Field(
        default=None,
        max_length=128,
        description="Optional Etherscan V2 key for this request only. Not stored with the report.",
    )

    @field_validator("etherscan_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ScanSummary(BaseModel):
    id: str
    score: int
    score_kind: str = "heuristic_penalty"
    verdict: str = "clean"
    verdict_label: str = "No detector hits"
    critical: int
    high: int
    medium: int
    low: int
    info: int
    findings: list[dict]
    contracts: list[dict]
    functions: list[dict]
    onchain: dict | None = None
    filename: str
    network: str
    address: str | None = None
    verified: bool
    compiler_errors: list[str]


def result_to_summary(scan_id: str, result: ScanResult, muted_keys: set[str] | None = None) -> dict:
    card = result.scorecard
    payload = result.to_dict()
    payload["id"] = scan_id
    keys = muted_keys or set()
    for item in payload.get("findings") or []:
        if not isinstance(item, dict):
            continue
        key = f"{item.get('id') or ''}|{item.get('contract') or ''}|{item.get('function') or ''}"
        item["muted"] = key in keys
    if keys:
        active = [
            Finding.from_dict(item)
            for item in payload.get("findings") or []
            if isinstance(item, dict) and not item.get("muted")
        ]
        card = compute_score(active)
        payload["scorecard"] = card.to_dict()
    payload["score"] = card.score
    payload["score_kind"] = card.score_kind
    payload["verdict"] = card.verdict
    payload["verdict_label"] = card.verdict_label
    payload["critical"] = card.critical
    payload["high"] = card.high
    payload["medium"] = card.medium
    payload["low"] = card.low
    payload["info"] = card.info
    return payload
