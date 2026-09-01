"""Human-readable Markdown scan report."""

from __future__ import annotations

from pathlib import Path

from scanner.models import ScanResult


def render_markdown(result: ScanResult) -> str:
    names = ", ".join(c.name for c in result.contracts) or result.filename
    card = result.scorecard
    lines: list[str] = [
        f"# ChainSentry report — {names}",
        "",
        f"**Verdict:** {card.verdict_label}  ",
        "Heuristic AST scan. Severity mix is the report — not a calibrated 0–100 rating.",
        "",
        f"- File: `{result.filename}`",
        f"- Network: {result.network}",
        f"- solc: {result.solc_version or 'n/a'}",
    ]
    if result.address:
        lines.append(f"- Address: `{result.address}`")
    if result.source_role == "implementation" and result.implementation_address:
        extra = f" ({result.analyzed_name})" if result.analyzed_name else ""
        lines.append(
            f"- Proxy → analyzed implementation `{result.implementation_address}`{extra}"
        )
    elif result.source_role == "proxy_fallback" and result.proxy_note:
        lines.append(f"- {result.proxy_note}")
    lines.extend(
        [
            "",
            "| Severity | Count |",
            "|---|---|",
            f"| Critical | {card.critical} |",
            f"| High | {card.high} |",
            f"| Medium | {card.medium} |",
            f"| Low | {card.low} |",
            f"| Info | {card.info} |",
            "",
        ]
    )
    if card.categories:
        lines.append("## Categories")
        lines.append("")
        for cat in card.categories:
            n = cat.finding_count
            lines.append(f"- **{cat.name}:** {n} finding{'s' if n != 1 else ''}")
        lines.append("")

    if result.compiler_errors:
        lines.extend(["## Compiler errors", ""])
        for err in result.compiler_errors:
            lines.append(f"```\n{err}\n```")
            lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not result.findings:
        lines.append("No issues detected by the current detector set.")
        lines.append("")
    else:
        for finding in result.findings:
            loc = f"{finding.location.file}:{finding.location.line}"
            fn = finding.function or "—"
            lines.append(
                f"### {finding.severity.value.upper()} — {finding.title} (`{finding.id}`)"
            )
            lines.append("")
            lines.append(
                f"**{finding.contract or names}** · `{loc}` · `{fn}()` · "
                f"{finding.classification} · confidence {finding.confidence}%"
            )
            lines.append("")
            lines.append(finding.description)
            lines.append("")
            if finding.snippet:
                lines.append("```solidity")
                start = finding.snippet_start_line or finding.location.line
                for offset, raw in enumerate(finding.snippet.splitlines()):
                    number = start + offset
                    mark = ">" if number == finding.location.line else " "
                    lines.append(f"{mark} {number:>4} | {raw}")
                lines.append("```")
                lines.append("")
            lines.append(f"**Fix:** {finding.recommendation}")
            lines.append("")

    if result.surfaces:
        lines.extend(
            [
                "## Function attack surface",
                "",
                "| Function | Visibility | Mutability | Risk | Notes |",
                "|---|---|---|---|---|",
            ]
        )
        for surface in result.surfaces:
            notes = "; ".join(surface.notes).replace("|", "\\|")
            lines.append(
                f"| `{surface.name}()` | {surface.visibility} | {surface.mutability} | "
                f"{surface.risk} | {notes} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(result: ScanResult, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(result), encoding="utf-8")
    return output
