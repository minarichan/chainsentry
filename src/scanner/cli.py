"""Command-line interface: `python -m scanner scan ...` / `scanner scan ...`."""

from __future__ import annotations

from pathlib import Path

import click

from scanner.settings import load_environment

load_environment()

from scanner.engine import scan_file, scan_verified, summarize_contract
from scanner.etherscan import SourceNotVerifiedError, UnsupportedCompilerError
from scanner.models import ScanResult, Severity
from scanner.onchain import analyze_address
from scanner.proxy import apply_scan_target, fetch_scan_target
from scanner.reporting import (
    write_html_report,
    write_json_report,
    write_markdown_report,
    write_sarif_report,
)

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def _filter_severity(result: ScanResult, minimum: str | None) -> ScanResult:
    if not minimum:
        return result
    threshold = SEVERITY_ORDER[minimum.lower()]
    result.findings = [
        f for f in result.findings if SEVERITY_ORDER[f.severity.value] <= threshold
    ]
    return result


def _print_console(result: ScanResult) -> None:
    click.echo("")
    for line in summarize_contract(result):
        click.echo(line)
    if result.compiler_errors:
        raise SystemExit(2)

    card = result.scorecard
    if result.source_role == "implementation" and result.implementation_address:
        click.echo(
            f"Proxy {result.address} → analyzed implementation "
            f"{result.implementation_address}"
            + (f" ({result.analyzed_name})" if result.analyzed_name else "")
        )
    elif result.source_role == "proxy_fallback":
        click.secho(
            result.proxy_note or "Proxy detected; scanned proxy source (implementation unavailable).",
            fg="yellow",
        )
    click.echo(f"Verdict: {card.verdict_label}")
    click.echo("  Heuristic AST scan — severity mix is the report, not a 0–100 rating.")
    click.echo(f"  Critical: {card.critical}")
    click.echo(f"  High:     {card.high}")
    click.echo(f"  Medium:   {card.medium}")
    click.echo(f"  Low:      {card.low}")
    click.echo(f"  Info:     {card.info}")
    click.echo("")
    for cat in card.categories:
        n = cat.finding_count
        click.echo(f"  {cat.name:<20} {n} finding{'s' if n != 1 else ''}")
    click.echo("")

    if not result.findings:
        click.secho("No findings.", fg="green")
        return

    click.echo("Findings")
    click.echo("-" * 40)
    for finding in result.findings:
        color = {
            Severity.CRITICAL: "red",
            Severity.HIGH: "red",
            Severity.MEDIUM: "yellow",
            Severity.LOW: "cyan",
            Severity.INFO: "blue",
        }[finding.severity]
        click.secho(
            f"{finding.severity.value.upper():<8} {finding.title}  [{finding.id}]",
            fg=color,
            bold=True,
        )
        click.echo(f"         {finding.function or '-'} · {finding.location.file}:{finding.location.line}  ({finding.classification})")
        click.echo(f"         {finding.description}")
        if finding.snippet:
            start = finding.snippet_start_line or finding.location.line
            for offset, raw in enumerate(finding.snippet.splitlines()):
                number = start + offset
                mark = ">" if number == finding.location.line else " "
                click.echo(f"       {mark} {number:>4} | {raw}")
        click.echo(f"         Fix: {finding.recommendation}")
        click.echo("")

    click.echo("Function attack surface")
    click.echo("-" * 40)
    for surface in result.surfaces:
        click.echo(f"{surface.name}()  risk={surface.risk}  [{', '.join(surface.notes)}]")


@click.group()
def main() -> None:
    """Static security analyzer for Solidity smart contracts."""


@main.command()
@click.argument("path", required=False)
@click.option("--address", "address", default=None, help="Verified contract address (Sourcify / Etherscan / Blockscout).")
@click.option(
    "--chain-id",
    "chain_id",
    type=click.Choice(["1", "8453", "42161"]),
    default=None,
    help="EVM chain: 1 Ethereum, 8453 Base, 42161 Arbitrum One. Default: ETHERSCAN_CHAIN_ID or 1.",
)
@click.option("--format", "fmt", type=click.Choice(["console", "json", "html", "markdown", "sarif", "all"]), default="console")
@click.option("--severity", type=click.Choice(["critical", "high", "medium", "low", "info"]), default=None)
@click.option("--output", "output_dir", default="reports", show_default=True)
@click.option("--fail-on", type=click.Choice(["critical", "high", "medium", "low"]), default=None, help="Exit 1 if findings at this severity or worse exist.")
def scan(
    path: str | None,
    address: str | None,
    chain_id: str | None,
    fmt: str,
    severity: str | None,
    output_dir: str,
    fail_on: str | None,
) -> None:
    """Scan a local .sol file or a verified on-chain contract."""
    onchain = None
    if address:
        from scanner.chains import resolve_chain

        spec = resolve_chain(int(chain_id) if chain_id else None)
        try:
            target = fetch_scan_target(address, chain_id=spec.id)
        except (SourceNotVerifiedError, UnsupportedCompilerError) as exc:
            click.secho(str(exc), fg="red")
            raise SystemExit(3) from exc
        result = apply_scan_target(scan_verified(target.analyzed, network=spec.network), target)
        try:
            onchain = analyze_address(
                address,
                verified=True,
                rpc_url=spec.rpc_url(),
                network=spec.network,
                chain_id=spec.id,
            )
            if target.implementation:
                onchain.implementation = onchain.implementation or target.implementation
                onchain.is_proxy = True
            result.onchain = onchain
        except Exception as exc:
            click.secho(f"On-chain analysis skipped: {exc}", fg="yellow")
    elif path:
        result = scan_file(path)
        result.network = "Local"
    else:
        raise click.UsageError("Provide a Solidity file path or --address.")

    result = _filter_severity(result, severity)
    out = Path(output_dir)
    stem = Path(result.filename).stem

    if fmt in {"json", "all"}:
        written = write_json_report(result, out / f"{stem}.json")
        click.echo(f"Wrote {written}")
    if fmt in {"html", "all"}:
        written = write_html_report(result, out / f"{stem}.html")
        click.echo(f"Wrote {written}")
    if fmt in {"markdown", "all"}:
        written = write_markdown_report(result, out / f"{stem}.md")
        click.echo(f"Wrote {written}")
    if fmt in {"sarif", "all"}:
        written = write_sarif_report(result, out / f"{stem}.sarif")
        click.echo(f"Wrote {written}")
    if fmt in {"console", "all"}:
        _print_console(result)

    if fail_on and result.findings:
        threshold = SEVERITY_ORDER[fail_on]
        if any(SEVERITY_ORDER[f.severity.value] <= threshold for f in result.findings):
            click.secho("\nSecurity scan failed.", fg="red", bold=True)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
