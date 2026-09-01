from scanner.etherscan import SourceNotVerifiedError, VerifiedContract
from scanner.engine import scan_verified
from scanner.proxy import apply_scan_target, fetch_scan_target, resolve_implementation_address

PROXY = "0x0000000000000000000000000000000000000001"
IMPL = "0x0000000000000000000000000000000000000002"


def _verified(address: str, name: str, *, is_proxy: bool = False, implementation: str | None = None) -> VerifiedContract:
    source = f"pragma solidity ^0.8.0; contract {name} {{ function ping() external {{}} }}"
    if name == "Logic":
        source = (
            "pragma solidity ^0.8.0; contract Logic { "
            "mapping(address => uint256) public balanceOf; "
            "function mint(address to, uint256 amount) external { balanceOf[to] += amount; } }"
        )
    return VerifiedContract(
        address=address,
        name=name,
        source=source,
        compiler_version="v0.8.20+commit.a1b79de6",
        solc_version="0.8.20",
        verified=True,
        sources={f"{name}.sol": source},
        primary_file=f"{name}.sol",
        is_proxy=is_proxy,
        implementation=implementation,
    )


def test_follows_explorer_implementation(monkeypatch) -> None:
    monkeypatch.setattr("scanner.proxy.read_eip1967_implementation", lambda *a, **k: None)

    def fake_fetch(address: str, api_key=None):
        if address.lower() == PROXY.lower():
            return _verified(PROXY, "Proxy", is_proxy=True, implementation=IMPL)
        return _verified(IMPL, "Logic")

    monkeypatch.setattr("scanner.proxy.fetch_verified_source", fake_fetch)
    target = fetch_scan_target(PROXY)
    assert target.source_role == "implementation"
    assert target.analyzed.name == "Logic"
    assert target.requested.lower() == PROXY.lower()
    assert target.implementation.lower() == IMPL.lower()

    result = apply_scan_target(scan_verified(target.analyzed), target)
    assert result.address.lower() == PROXY.lower()
    assert result.source_role == "implementation"
    assert result.analyzed_name == "Logic"
    assert any(c.name == "Logic" for c in result.contracts)
    assert any(f.id == "SC-ACCESS-001" for f in result.findings)


def test_falls_back_when_implementation_unverified(monkeypatch) -> None:
    monkeypatch.setattr("scanner.proxy.read_eip1967_implementation", lambda *a, **k: None)

    def fake_fetch(address: str, api_key=None):
        if address.lower() == PROXY.lower():
            return _verified(PROXY, "Proxy", is_proxy=True, implementation=IMPL)
        raise SourceNotVerifiedError("impl not verified")

    monkeypatch.setattr("scanner.proxy.fetch_verified_source", fake_fetch)
    target = fetch_scan_target(PROXY)
    assert target.source_role == "proxy_fallback"
    assert target.analyzed.name == "Proxy"
    assert target.note and "not verified" in target.note.lower()


def test_no_follow_without_implementation(monkeypatch) -> None:
    monkeypatch.setattr("scanner.proxy.read_eip1967_implementation", lambda *a, **k: None)
    monkeypatch.setattr(
        "scanner.proxy.fetch_verified_source",
        lambda address, api_key=None: _verified(address, "Plain"),
    )
    target = fetch_scan_target(PROXY)
    assert target.source_role == "declared"
    assert target.implementation is None


def test_eip1967_used_when_explorer_omits_impl(monkeypatch) -> None:
    monkeypatch.setattr("scanner.proxy.read_eip1967_implementation", lambda *a, **k: IMPL)

    def fake_fetch(address: str, api_key=None):
        if address.lower() == PROXY.lower():
            return _verified(PROXY, "Proxy", is_proxy=True, implementation=None)
        return _verified(IMPL, "Logic")

    monkeypatch.setattr("scanner.proxy.fetch_verified_source", fake_fetch)
    target = fetch_scan_target(PROXY)
    assert target.source_role == "implementation"
    assert target.implementation.lower() == IMPL.lower()


def test_resolve_ignores_self_implementation(monkeypatch) -> None:
    monkeypatch.setattr("scanner.proxy.read_eip1967_implementation", lambda *a, **k: None)
    verified = _verified(PROXY, "Proxy", is_proxy=True, implementation=PROXY)
    assert resolve_implementation_address(verified, PROXY) is None
