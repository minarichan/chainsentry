"""Finding counts and a heuristic penalty remainder — not a calibrated risk rating."""

from __future__ import annotations

from collections import defaultdict

from scanner.models import CategoryScore, Finding, ScoreCard, Severity

SEVERITY_PENALTY = {
    Severity.CRITICAL: 30,
    Severity.HIGH: 15,
    Severity.MEDIUM: 7,
    Severity.LOW: 3,
    Severity.INFO: 1,
}

CATEGORY_BY_ID = {
    "SC-ACCESS-001": "Access Control",
    "SC-TXORIGIN-001": "Access Control",
    "SC-REENTRANCY-001": "Reentrancy",
    "SC-REENTRANCY-002": "Reentrancy",
    "SC-UNCHECKED-001": "External Calls",
    "SC-DELEGATECALL-001": "External Calls",
    "SC-SELFDESTRUCT-001": "External Calls",
    "SC-TIMESTAMP-001": "Input Validation",
    "SC-RANDOMNESS-001": "Input Validation",
    "SC-ERC20-001": "External Calls",
    "SC-INIT-001": "Access Control",
    "SC-TRANSFERFROM-001": "Access Control",
}

ALL_CATEGORIES = (
    "Access Control",
    "Reentrancy",
    "External Calls",
    "Input Validation",
)

VERDICT_LABELS = {
    "failed": "Not analyzed",
    "issues": "Issues found",
    "review": "Review suggested",
    "notes": "Notes only",
    "clean": "No detector hits",
}


def verdict_from_counts(
    *,
    critical: int,
    high: int,
    medium: int,
    low: int,
    info: int,
    compiled: bool = True,
) -> tuple[str, str]:
    """Map severity mix to a label. Does not use the 0–100 penalty figure."""
    if not compiled:
        return "failed", VERDICT_LABELS["failed"]
    if critical or high:
        return "issues", VERDICT_LABELS["issues"]
    if medium:
        return "review", VERDICT_LABELS["review"]
    if low or info:
        return "notes", VERDICT_LABELS["notes"]
    return "clean", VERDICT_LABELS["clean"]


def failed_scorecard() -> ScoreCard:
    key, label = verdict_from_counts(
        critical=0, high=0, medium=0, low=0, info=0, compiled=False
    )
    return ScoreCard(
        score=0,
        verdict=key,
        verdict_label=label,
        score_kind="heuristic_penalty",
    )


def compute_score(findings: list[Finding]) -> ScoreCard:
    counts = {s: 0 for s in Severity}
    penalty = 0
    by_category: dict[str, list[Finding]] = defaultdict(list)

    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
        penalty += SEVERITY_PENALTY.get(finding.severity, 1)
        category = CATEGORY_BY_ID.get(finding.id, "Other")
        by_category[category].append(finding)

    critical = counts.get(Severity.CRITICAL, 0)
    high = counts.get(Severity.HIGH, 0)
    medium = counts.get(Severity.MEDIUM, 0)
    low = counts.get(Severity.LOW, 0)
    info = counts.get(Severity.INFO, 0)
    verdict, verdict_label = verdict_from_counts(
        critical=critical, high=high, medium=medium, low=low, info=info
    )

    categories: list[CategoryScore] = []
    for name in ALL_CATEGORIES:
        cat_findings = by_category.get(name, [])
        cat_penalty = sum(SEVERITY_PENALTY.get(f.severity, 1) for f in cat_findings)
        categories.append(
            CategoryScore(
                name=name,
                score=max(0, min(100, 100 - cat_penalty)),
                finding_count=len(cat_findings),
            )
        )

    return ScoreCard(
        score=max(0, min(100, 100 - penalty)),
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        info=info,
        categories=categories,
        verdict=verdict,
        verdict_label=verdict_label,
        score_kind="heuristic_penalty",
    )
