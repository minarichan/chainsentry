"""End-to-end scan pipeline: compile → parse → detect → score → surface."""

from __future__ import annotations

from pathlib import Path

from scanner.attack_surface import analyze_contract
from scanner.compiler import CompilationResult, compile_file, compile_source, compile_sources
from scanner.detectors import all_detectors
from scanner.etherscan import VerifiedContract
from scanner.models import Finding, ScanResult, Severity
from scanner.parser import (
    inherited_base_ids,
    is_analyzable_kind,
    is_inherited_base,
    parse_compilation,
)
from scanner.scoring import compute_score, failed_scorecard
from scanner.snippets import attach_snippets


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Keep one finding per detector + issue text + line.

    Location.file is ignored: the same function is often parsed from a base
    contract and from each child file, so the path differs while the card looks
    identical (same title, function, line, and description).
    """
    grouped: dict[tuple, Finding] = {}
    order: list[tuple] = []
    for finding in findings:
        key = (
            finding.id,
            (finding.function or "").lower(),
            finding.location.line,
            (finding.description or "").strip(),
        )
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = finding
            order.append(key)
            continue
        names: list[str] = []
        for name in (existing.contract, finding.contract):
            if name and name not in names:
                names.append(name)
        if names:
            existing.contract = ", ".join(names)
    return [grouped[key] for key in order]


def _fn_key(finding: Finding) -> tuple[str, str]:
    contract = (finding.contract or "").split(",")[0].strip().lower()
    return contract, (finding.function or "").lower()


# More specific checks win when they fire on the same function. ACCESS/TIMESTAMP
# often repeat the same story (drain, entropy) as another HIGH card.
_ACCESS_COVERED_BY = {
    "SC-TXORIGIN-001",
    "SC-SELFDESTRUCT-001",
    "SC-RANDOMNESS-001",
    "SC-INIT-001",
}
_REENTRANCY_IDS = {"SC-REENTRANCY-001", "SC-REENTRANCY-002"}


def _collapse_overlaps(findings: list[Finding]) -> list[Finding]:
    """Drop pile-on findings that restate a more specific hit on the same function."""
    by_fn: dict[tuple[str, str], set[str]] = {}
    for finding in findings:
        by_fn.setdefault(_fn_key(finding), set()).add(finding.id)

    kept: list[Finding] = []
    for finding in findings:
        ids = by_fn.get(_fn_key(finding), set())
        if finding.id == "SC-TIMESTAMP-001" and "SC-RANDOMNESS-001" in ids:
            continue
        if finding.id == "SC-DELEGATECALL-001" and ids & _REENTRANCY_IDS:
            continue
        if finding.id == "SC-ACCESS-001" and ids & _ACCESS_COVERED_BY:
            continue
        kept.append(finding)
    return kept


def _run_detectors(compilation: CompilationResult) -> ScanResult:
    contracts = parse_compilation(compilation)
    findings: list[Finding] = []
    surfaces = []
    detectors = all_detectors()
    base_ids = inherited_base_ids(contracts)

    for contract in contracts:
        if not is_analyzable_kind(contract.kind):
            continue
        if is_inherited_base(contract, base_ids):
            continue
        for detector in detectors:
            findings.extend(detector.detect(contract))
        surfaces.extend(analyze_contract(contract))

    findings = _collapse_overlaps(_dedupe_findings(findings))
    attach_snippets(
        findings,
        contracts,
        file_sources=compilation.file_sources,
        fallback_source=compilation.source,
    )
    findings.sort(key=lambda f: ({
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }[f.severity], f.location.line))

    if not compilation.success:
        scorecard = failed_scorecard()
    else:
        scorecard = compute_score(findings)

    return ScanResult(
        contracts=contracts,
        findings=findings,
        scorecard=scorecard,
        surfaces=surfaces,
        filename=compilation.filename,
        solc_version=compilation.solc_version,
        source=compilation.source,
        compiler_errors=compilation.errors,
        verified=compilation.success,
    )


def scan_source(source: str, filename: str = "Contract.sol") -> ScanResult:
    compilation = compile_source(source, filename=filename)
    return _run_detectors(compilation)


def scan_file(path: str | Path) -> ScanResult:
    compilation = compile_file(str(path))
    return _run_detectors(compilation)


def scan_verified(verified: VerifiedContract, *, network: str = "Ethereum Mainnet") -> ScanResult:
    sources = verified.sources or {verified.primary_file: verified.source}
    compilation = compile_sources(
        sources,
        filename=verified.primary_file,
        solc_version=verified.solc_version or None,
        optimizer=verified.optimizer,
        remappings=verified.remappings or None,
        evm_version=verified.evm_version,
        via_ir=bool(verified.via_ir),
    )
    result = _run_detectors(compilation)
    result.address = verified.address
    result.network = network
    result.verified = compilation.success
    return result


def summarize_contract(result: ScanResult) -> list[str]:
    """Stage-1 style summary lines."""
    lines: list[str] = []
    if result.compiler_errors:
        lines.append("Compilation failed:")
        lines.extend(f"  {err}" for err in result.compiler_errors)
        return lines
    for contract in result.contracts:
        lines.append(f"Contract: {contract.name}")
        lines.append(f"Functions: {len(contract.functions)}")
        lines.append(f"State Variables: {len(contract.state_variables)}")
        lines.append(f"Modifiers: {len(contract.modifiers)}")
        lines.append(f"Events: {len(contract.events)}")
        if contract.inheritance:
            lines.append(f"Inheritance: {', '.join(contract.inheritance)}")
        lines.append("")
    return lines
