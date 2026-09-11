import pytest

from scanner.lookup import (
    InvalidScanTargetError,
    NameNotResolvedError,
    ResolvedTarget,
    resolve_ens_name,
    resolve_scan_input,
)


def test_checksums_hex_address() -> None:
    resolved = resolve_scan_input("0x0000000000000000000000000000000000000001")
    assert resolved.address == "0x0000000000000000000000000000000000000001"
    assert resolved.lookup is None


def test_rejects_short_hex() -> None:
    with pytest.raises(InvalidScanTargetError, match="not a valid address"):
        resolve_scan_input("0x1234")


def test_rejects_bare_word() -> None:
    with pytest.raises(InvalidScanTargetError, match="ENS name"):
        resolve_scan_input("uniswap")


def test_resolves_ens_name(monkeypatch) -> None:
    monkeypatch.setattr(
        "scanner.lookup.resolve_ens_name",
        lambda name, rpc_url=None: "0x0000000000000000000000000000000000000001",
    )
    resolved = resolve_scan_input("Example.ETH")
    assert resolved == ResolvedTarget("0x0000000000000000000000000000000000000001", "example.eth")


def test_missing_ens_name(monkeypatch) -> None:
    monkeypatch.setattr("scanner.lookup.resolve_ens_name", lambda name, rpc_url=None: None)
    with pytest.raises(NameNotResolvedError, match="no address"):
        resolve_scan_input("missing.eth")


def test_ens_rpc_failure(monkeypatch) -> None:
    def boom(name, rpc_url=None):
        raise RuntimeError("525 Server Error: <none> for url: https://eth.llamarpc.com/")

    monkeypatch.setattr("scanner.lookup.resolve_ens_name", boom)
    with pytest.raises(NameNotResolvedError, match="did not respond") as caught:
        resolve_scan_input("vitalik.eth")
    assert "llamarpc" not in str(caught.value)
    assert "525" not in str(caught.value)


def test_ens_retries_next_rpc(monkeypatch) -> None:
    calls: list[str] = []

    def fake(name, url):
        calls.append(url)
        if "llamarpc" in url:
            raise RuntimeError("525 Server Error: <none> for url: https://eth.llamarpc.com/")
        return "0x0000000000000000000000000000000000000001"

    monkeypatch.setenv("ETH_RPC_URL", "https://eth.llamarpc.com")
    monkeypatch.setattr("scanner.lookup._ens_address_via", fake)
    assert resolve_ens_name("example.eth") == "0x0000000000000000000000000000000000000001"
    assert any("llamarpc" in url for url in calls)
    assert len(calls) >= 2
