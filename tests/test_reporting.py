from pathlib import Path

from scanner.engine import scan_file
from scanner.reporting import (
    render_markdown,
    render_sarif,
    write_html_report,
    write_json_report,
    write_markdown_report,
    write_sarif_report,
)

ROOT = Path(__file__).resolve().parents[1]


def test_json_and_html_reports(tmp_path: Path) -> None:
    result = scan_file(ROOT / "contracts" / "vulnerable" / "Reentrancy.sol")
    json_path = write_json_report(result, tmp_path / "report.json")
    html_path = write_html_report(result, tmp_path / "report.html")
    assert json_path.exists()
    assert "SC-REENTRANCY-001" in json_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    assert "Security Report" in html
    assert "Potential Reentrancy" in html
    assert "snippet" in html
    assert ".call" in html
    assert "Issues found" in html
    assert "heuristic" in html.lower()
    assert "Security score" not in html
    assert "/100" not in html

    md_path = write_markdown_report(result, tmp_path / "report.md")
    markdown = md_path.read_text(encoding="utf-8")
    assert markdown.startswith("# ChainSentry report")
    assert "SC-REENTRANCY-001" in markdown
    assert "Potential Reentrancy" in markdown
    assert "```solidity" in markdown
    assert "Security score" not in markdown
    assert render_markdown(result) == markdown

    sarif_path = write_sarif_report(result, tmp_path / "report.sarif")
    payload = render_sarif(result)
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["tool"]["driver"]["name"] == "ChainSentry"
    rule_ids = {rule["id"] for rule in payload["runs"][0]["tool"]["driver"]["rules"]}
    assert "SC-REENTRANCY-001" in rule_ids
    assert "SC-REENTRANCY-002" in rule_ids
    assert "SC-ERC20-001" in rule_ids
    hits = payload["runs"][0]["results"]
    assert any(item["ruleId"] == "SC-REENTRANCY-001" for item in hits)
    assert any(item["level"] == "error" for item in hits)
    assert "SC-REENTRANCY-001" in sarif_path.read_text(encoding="utf-8")


def test_withdraw_attack_surface_is_high() -> None:
    result = scan_file(ROOT / "contracts" / "vulnerable" / "Reentrancy.sol")
    withdraw = next(s for s in result.surfaces if s.name == "withdraw")
    assert withdraw.risk == "HIGH"
    assert withdraw.has_external_call
    assert withdraw.sends_eth
