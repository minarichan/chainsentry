from pydantic import BaseModel, Field

from scanner.models import ScanResult


class ScanRequest(BaseModel):
    source: str | None = Field(default=None, description="Solidity source code")
    filename: str = "Contract.sol"
    address: str | None = Field(default=None, description="Verified Ethereum contract address")
    include_onchain: bool = True


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


def result_to_summary(scan_id: str, result: ScanResult) -> dict:
    card = result.scorecard
    payload = result.to_dict()
    payload["id"] = scan_id
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
