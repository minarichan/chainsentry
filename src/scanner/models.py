"""Shared data structures used by the scanner, API, and reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Parameter:
    name: str
    type: str


@dataclass
class Function:
    name: str
    visibility: str
    mutability: str
    parameters: list[Parameter] = field(default_factory=list)
    return_values: list[Parameter] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)
    is_constructor: bool = False
    is_fallback: bool = False
    is_receive: bool = False
    line: int = 0
    src_offset: int = 0
    ast: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class StateVariable:
    name: str
    type: str
    visibility: str
    is_constant: bool = False
    is_immutable: bool = False
    line: int = 0
    ast: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Event:
    name: str
    parameters: list[Parameter] = field(default_factory=list)
    line: int = 0


@dataclass
class Modifier:
    name: str
    parameters: list[Parameter] = field(default_factory=list)
    line: int = 0
    ast: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Contract:
    name: str
    kind: str
    filename: str
    source: str
    inheritance: list[str] = field(default_factory=list)
    functions: list[Function] = field(default_factory=list)
    state_variables: list[StateVariable] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    modifiers: list[Modifier] = field(default_factory=list)
    line: int = 0
    ast: dict[str, Any] = field(default_factory=dict, repr=False)
    abi: list[dict[str, Any]] = field(default_factory=list)

    def function_by_name(self, name: str) -> Optional[Function]:
        for fn in self.functions:
            if fn.name == name:
                return fn
        return None

    @property
    def state_variable_names(self) -> set[str]:
        return {v.name for v in self.state_variables}


@dataclass
class Location:
    file: str
    line: int
    column: int = 0
    end_line: Optional[int] = None


@dataclass
class Finding:
    id: str
    title: str
    severity: Severity
    confidence: int
    description: str
    location: Location
    function: Optional[str]
    recommendation: str
    classification: str
    contract: Optional[str] = None
    snippet: Optional[str] = None
    snippet_start_line: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "description": self.description,
            "location": {
                "file": self.location.file,
                "line": self.location.line,
                "column": self.location.column,
                "end_line": self.location.end_line,
            },
            "function": self.function,
            "recommendation": self.recommendation,
            "classification": self.classification,
            "contract": self.contract,
            "snippet": self.snippet,
            "snippet_start_line": self.snippet_start_line,
        }


@dataclass
class FunctionSurface:
    name: str
    contract: str
    visibility: str
    mutability: str
    payable: bool
    modifies_state: bool
    has_external_call: bool
    sends_eth: bool
    has_reentrancy_guard: bool
    has_access_control: bool
    risk: str
    notes: list[str] = field(default_factory=list)
    line: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "contract": self.contract,
            "visibility": self.visibility,
            "mutability": self.mutability,
            "payable": self.payable,
            "modifies_state": self.modifies_state,
            "has_external_call": self.has_external_call,
            "sends_eth": self.sends_eth,
            "has_reentrancy_guard": self.has_reentrancy_guard,
            "has_access_control": self.has_access_control,
            "risk": self.risk,
            "notes": self.notes,
            "line": self.line,
        }


@dataclass
class CategoryScore:
    name: str
    score: int
    finding_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "finding_count": self.finding_count,
        }


@dataclass
class ScoreCard:
    score: int
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    categories: list[CategoryScore] = field(default_factory=list)
    verdict: str = "clean"
    verdict_label: str = "No detector hits"
    score_kind: str = "heuristic_penalty"

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "score_kind": self.score_kind,
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "critical": self.critical,
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
            "info": self.info,
            "categories": [c.to_dict() for c in self.categories],
        }


@dataclass
class OnChainAnalysis:
    address: str
    network: str
    verified: bool
    transaction_count: Optional[int] = None
    unique_users: Optional[int] = None
    eth_balance: Optional[str] = None
    is_proxy: bool = False
    implementation: Optional[str] = None
    has_privileged_owner: bool = False
    owner: Optional[str] = None
    signals: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "network": self.network,
            "verified": self.verified,
            "transaction_count": self.transaction_count,
            "unique_users": self.unique_users,
            "eth_balance": self.eth_balance,
            "is_proxy": self.is_proxy,
            "implementation": self.implementation,
            "has_privileged_owner": self.has_privileged_owner,
            "owner": self.owner,
            "signals": self.signals,
            "notes": self.notes,
        }


@dataclass
class ScanResult:
    contracts: list[Contract]
    findings: list[Finding]
    scorecard: ScoreCard
    surfaces: list[FunctionSurface]
    filename: str
    solc_version: str
    source: str
    network: str = "Local"
    address: Optional[str] = None
    verified: bool = True
    onchain: Optional[OnChainAnalysis] = None
    compiler_errors: list[str] = field(default_factory=list)
    implementation_address: Optional[str] = None
    analyzed_address: Optional[str] = None
    analyzed_name: Optional[str] = None
    source_role: str = "declared"
    proxy_note: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "solc_version": self.solc_version,
            "network": self.network,
            "address": self.address,
            "implementation_address": self.implementation_address,
            "analyzed_address": self.analyzed_address,
            "analyzed_name": self.analyzed_name,
            "source_role": self.source_role,
            "proxy_note": self.proxy_note,
            "verified": self.verified,
            "contracts": [
                {
                    "name": c.name,
                    "kind": c.kind,
                    "inheritance": c.inheritance,
                    "functions": len(c.functions),
                    "state_variables": len(c.state_variables),
                    "events": len(c.events),
                    "modifiers": len(c.modifiers),
                    "line": c.line,
                }
                for c in self.contracts
            ],
            "scorecard": self.scorecard.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "functions": [s.to_dict() for s in self.surfaces],
            "onchain": self.onchain.to_dict() if self.onchain else None,
            "compiler_errors": self.compiler_errors,
        }
