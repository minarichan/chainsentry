"""Attach ±N source lines to findings for report cards."""

from __future__ import annotations

from scanner.models import Contract, Finding

CONTEXT = 5


def extract_snippet(source: str, line: int, context: int = CONTEXT) -> tuple[str, int]:
    """Return (text, first_line_number). Empty if the source or line is unusable."""
    if not source or line < 1:
        return "", 0
    lines = source.splitlines()
    if not lines:
        return "", 0
    target = min(line, len(lines))
    start = max(1, target - context)
    end = min(len(lines), target + context)
    return "\n".join(lines[start - 1 : end]), start


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _source_for(finding: Finding, contracts: list[Contract], file_sources: dict[str, str], fallback: str) -> str:
    path = finding.location.file or ""
    wanted = _norm(path)
    if path in file_sources:
        return file_sources[path]
    if wanted:
        for name, src in file_sources.items():
            key = _norm(name)
            if key == wanted or key.endswith("/" + wanted) or wanted.endswith("/" + key):
                return src
    names = {part.strip() for part in (finding.contract or "").split(",") if part.strip()}
    for contract in contracts:
        if path and _norm(contract.filename) == wanted and contract.source:
            return contract.source
        if contract.name in names and contract.source:
            return contract.source
    if file_sources:
        return next(iter(file_sources.values()))
    return fallback


def attach_snippets(
    findings: list[Finding],
    contracts: list[Contract],
    file_sources: dict[str, str] | None = None,
    fallback_source: str = "",
) -> list[Finding]:
    sources = file_sources or {}
    for finding in findings:
        if finding.snippet:
            continue
        source = _source_for(finding, contracts, sources, fallback_source)
        text, start = extract_snippet(source, finding.location.line)
        finding.snippet = text or None
        finding.snippet_start_line = start
    return findings
