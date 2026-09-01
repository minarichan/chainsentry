from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import CONTRACTS

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_scan_requires_input() -> None:
    response = client.post("/scan", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "Provide source or address."
    assert "`" not in response.json()["detail"]


def test_scan_source() -> None:
    source = (CONTRACTS / "vulnerable" / "TxOrigin.sol").read_text(encoding="utf-8")
    response = client.post("/scan", json={"source": source, "filename": "TxOrigin.sol", "include_onchain": False})
    assert response.status_code == 200
    body = response.json()
    assert body["high"] >= 1
    assert body["verdict"] == "issues"
    assert body["score_kind"] == "heuristic_penalty"
    assert any(f["id"] == "SC-TXORIGIN-001" for f in body["findings"])
    scan_id = body["id"]
    fetched = client.get(f"/scan/{scan_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == scan_id

    markdown = client.get(f"/scan/{scan_id}/report.md")
    assert markdown.status_code == 200
    assert "SC-TXORIGIN-001" in markdown.text
    assert markdown.headers["content-type"].startswith("text/markdown")

    sarif = client.get(f"/scan/{scan_id}/report.sarif")
    assert sarif.status_code == 200
    body = sarif.json()
    assert body["version"] == "2.1.0"
    assert any(item["ruleId"] == "SC-TXORIGIN-001" for item in body["runs"][0]["results"])


def test_scan_persists_in_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCAN_DB_PATH", str(tmp_path / "scans.sqlite"))
    source = (CONTRACTS / "vulnerable" / "TxOrigin.sol").read_text(encoding="utf-8")
    created = client.post(
        "/scan",
        json={"source": source, "filename": "TxOrigin.sol", "include_onchain": False},
    )
    assert created.status_code == 200
    scan_id = created.json()["id"]
    from api.store import load_scan

    stored = load_scan(scan_id)
    assert stored is not None
    assert any(f.id == "SC-TXORIGIN-001" for f in stored.findings)
    fetched = client.get(f"/scan/{scan_id}")
    assert fetched.status_code == 200
    markdown = client.get(f"/scan/{scan_id}/report.md")
    assert markdown.status_code == 200
    assert "SC-TXORIGIN-001" in markdown.text
