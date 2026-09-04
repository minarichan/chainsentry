from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import CONTRACTS

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "strict-origin-when-cross-origin" in response.headers["referrer-policy"]
    csp = response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    assert "default-src 'self'" in csp


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


def test_scan_rate_limit(monkeypatch) -> None:
    from api.limits import reset_limits_for_tests
    from api.routes import scan as scan_routes
    from scanner.models import ScanResult, ScoreCard

    monkeypatch.setenv("SCAN_RATE_PER_MIN", "1")
    monkeypatch.setenv("SCAN_RATE_PER_HOUR", "1")
    reset_limits_for_tests()

    def stub(_body):
        return ScanResult(
            contracts=[],
            findings=[],
            scorecard=ScoreCard(score=100),
            surfaces=[],
            filename="C.sol",
            solc_version="0.8.20",
            source="",
        )

    monkeypatch.setattr(scan_routes, "_execute_scan", stub)
    payload = {"source": "pragma solidity ^0.8.0; contract C {}", "filename": "C.sol", "include_onchain": False}
    first = client.post("/scan", json=payload)
    assert first.status_code == 200
    second = client.post("/scan", json=payload)
    assert second.status_code == 429
    assert "too many" in second.json()["detail"].lower()
    reset_limits_for_tests()


def test_scan_rejects_when_busy(monkeypatch) -> None:
    import threading

    from api.limits import reset_limits_for_tests
    from api.routes import scan as scan_routes
    from scanner.models import ScanResult, ScoreCard

    monkeypatch.setenv("SCAN_MAX_IN_FLIGHT", "1")
    monkeypatch.setenv("SCAN_RATE_PER_MIN", "0")
    monkeypatch.setenv("SCAN_TIMEOUT_SEC", "15")
    reset_limits_for_tests()
    started = threading.Event()
    release = threading.Event()

    def block(_body):
        started.set()
        release.wait(timeout=10)
        return ScanResult(
            contracts=[],
            findings=[],
            scorecard=ScoreCard(score=100),
            surfaces=[],
            filename="C.sol",
            solc_version="0.8.20",
            source="",
        )

    monkeypatch.setattr(scan_routes, "_execute_scan", block)
    worker = threading.Thread(
        target=lambda: client.post(
            "/scan",
            json={"source": "pragma solidity ^0.8.0; contract C {}", "filename": "C.sol", "include_onchain": False},
        )
    )
    worker.start()
    assert started.wait(timeout=5)
    blocked = client.post(
        "/scan",
        json={"source": "pragma solidity ^0.8.0; contract C {}", "filename": "C.sol", "include_onchain": False},
    )
    assert blocked.status_code == 503
    assert "busy" in blocked.json()["detail"].lower()
    release.set()
    worker.join(timeout=10)
    reset_limits_for_tests()


def test_scan_timeout(monkeypatch) -> None:
    import time

    from api.routes import scan as scan_routes

    monkeypatch.setenv("SCAN_TIMEOUT_SEC", "1")

    def hang(_body):
        time.sleep(8)
        raise AssertionError("scan should have been timed out")

    monkeypatch.setattr(scan_routes, "_execute_scan", hang)
    response = client.post(
        "/scan",
        json={"source": "pragma solidity ^0.8.0; contract C {}", "filename": "C.sol", "include_onchain": False},
    )
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_scan_rejects_unknown_chain() -> None:
    response = client.post(
        "/scan",
        json={"address": "0x0000000000000000000000000000000000000001", "chain_id": 10},
    )
    assert response.status_code == 422


def test_scan_passes_browser_etherscan_key(monkeypatch) -> None:
    from scanner.etherscan import SourceNotVerifiedError
    from api.routes import scan as scan_routes

    captured: dict[str, str | None] = {}

    def fake_target(address, api_key=None, chain_id=None):
        captured["api_key"] = api_key
        raise SourceNotVerifiedError("nope")

    monkeypatch.setattr(scan_routes, "fetch_scan_target", fake_target)
    response = client.post(
        "/scan",
        json={
            "address": "0x0000000000000000000000000000000000000001",
            "chain_id": 1,
            "include_onchain": False,
            "etherscan_api_key": "user-secret-key",
        },
    )
    assert response.status_code == 422
    assert captured["api_key"] == "user-secret-key"
    assert "user-secret-key" not in response.text


def test_scan_redacts_etherscan_key_on_502(monkeypatch) -> None:
    from api.routes import scan as scan_routes

    def fake_target(address, api_key=None, chain_id=None):
        raise RuntimeError(f"upstream rejected {api_key}")

    monkeypatch.setattr(scan_routes, "fetch_scan_target", fake_target)
    response = client.post(
        "/scan",
        json={
            "address": "0x0000000000000000000000000000000000000001",
            "chain_id": 1,
            "include_onchain": False,
            "etherscan_api_key": "user-secret-key",
        },
    )
    assert response.status_code == 502
    assert "user-secret-key" not in response.text
    assert "[redacted]" in response.json()["detail"]


def test_scan_does_not_persist_etherscan_key(tmp_path, monkeypatch) -> None:
    from api.limits import reset_limits_for_tests
    from api.routes import scan as scan_routes
    from scanner.models import ScanResult, ScoreCard

    monkeypatch.setenv("SCAN_DB_PATH", str(tmp_path / "scans.sqlite"))
    monkeypatch.setenv("SCAN_RATE_PER_MIN", "0")
    reset_limits_for_tests()

    def stub(_body):
        return ScanResult(
            contracts=[],
            findings=[],
            scorecard=ScoreCard(score=100, verdict="clean", verdict_label="No detector hits"),
            surfaces=[],
            filename="C.sol",
            solc_version="0.8.20",
            source="",
            address="0x0000000000000000000000000000000000000001",
            chain_id=1,
            network="Ethereum",
        )

    monkeypatch.setattr(scan_routes, "_execute_scan", stub)
    created = client.post(
        "/scan",
        json={
            "address": "0x0000000000000000000000000000000000000001",
            "include_onchain": False,
            "etherscan_api_key": "do-not-store-this-key",
        },
    )
    assert created.status_code == 200
    db = (tmp_path / "scans.sqlite").read_bytes()
    assert b"do-not-store-this-key" not in db
    assert "do-not-store-this-key" not in created.text
    reset_limits_for_tests()


def test_scan_passes_chain_id(monkeypatch) -> None:
    from scanner.etherscan import SourceNotVerifiedError
    from api.routes import scan as scan_routes

    captured: dict[str, int | None] = {}

    def fake_target(address, api_key=None, chain_id=None):
        captured["chain_id"] = chain_id
        raise SourceNotVerifiedError("nope")

    monkeypatch.setattr(scan_routes, "fetch_scan_target", fake_target)
    response = client.post(
        "/scan",
        json={
            "address": "0x0000000000000000000000000000000000000001",
            "chain_id": 8453,
            "include_onchain": False,
        },
    )
    assert response.status_code == 422
    assert captured["chain_id"] == 8453
    assert "nope" in response.json()["detail"]


def test_scan_unverified_address_is_422_not_500(monkeypatch) -> None:
    from scanner.etherscan import SourceNotVerifiedError
    from api.routes import scan as scan_routes

    def fake_target(address, api_key=None, chain_id=None):
        raise SourceNotVerifiedError(
            "No verified Solidity source on Sourcify, Blockscout for this chain. "
            "This demo uses Sourcify, then Blockscout; it has no Etherscan key."
        )

    monkeypatch.setattr(scan_routes, "fetch_scan_target", fake_target)
    response = client.post(
        "/scan",
        json={
            "address": "0x0000000000000000000000000000000000000001",
            "chain_id": 1,
            "include_onchain": False,
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Sourcify" in detail
    assert "500" not in detail


def test_mute_finding_and_rescan_same_address(tmp_path, monkeypatch) -> None:
    from api.limits import reset_limits_for_tests
    from api.routes import scan as scan_routes
    from scanner.models import Finding, Location, ScanResult, ScoreCard, Severity

    monkeypatch.setenv("SCAN_DB_PATH", str(tmp_path / "scans.sqlite"))
    monkeypatch.setenv("SCAN_RATE_PER_MIN", "0")
    reset_limits_for_tests()

    finding = Finding(
        id="SC-TXORIGIN-001",
        title="tx.origin",
        severity=Severity.HIGH,
        confidence=80,
        description="uses tx.origin",
        location=Location(file="C.sol", line=12),
        function="withdraw",
        recommendation="Use msg.sender",
        classification="SWC-115",
        contract="Vault",
    )

    def stub(_body):
        return ScanResult(
            contracts=[],
            findings=[finding],
            scorecard=ScoreCard(score=85, high=1, verdict="issues", verdict_label="Issues found"),
            surfaces=[],
            filename="C.sol",
            solc_version="0.8.20",
            source="",
            address="0x0000000000000000000000000000000000000001",
            chain_id=1,
            network="Ethereum",
        )

    monkeypatch.setattr(scan_routes, "_execute_scan", stub)
    first = client.post(
        "/scan",
        json={"address": "0x0000000000000000000000000000000000000001", "include_onchain": False},
    )
    assert first.status_code == 200
    scan_id = first.json()["id"]
    hit = first.json()["findings"][0]
    assert hit["muted"] is False
    muted = client.post(
        f"/scan/{scan_id}/mute",
        json={
            "finding_id": hit["id"],
            "contract": hit["contract"],
            "function": hit["function"],
            "muted": True,
        },
    )
    assert muted.status_code == 200
    assert muted.json()["findings"][0]["muted"] is True
    assert muted.json()["high"] == 0
    second = client.post(
        "/scan",
        json={"address": "0x0000000000000000000000000000000000000001", "include_onchain": False},
    )
    assert second.status_code == 200
    assert second.json()["findings"][0]["muted"] is True
    restored = client.post(
        f"/scan/{second.json()['id']}/mute",
        json={
            "finding_id": hit["id"],
            "contract": hit["contract"],
            "function": hit["function"],
            "muted": False,
        },
    )
    assert restored.status_code == 200
    assert restored.json()["findings"][0]["muted"] is False
    reset_limits_for_tests()
