from scanner.etherscan import SourceNotVerifiedError, VerifiedContract
from scanner.engine import scan_verified
from scanner.onchain import parse_eip1167_implementation
from scanner.proxy import apply_scan_target, fetch_scan_target, resolve_implementation_address

PROXY = "0x0000000000000000000000000000000000000001"
IMPL = "0x0000000000000000000000000000000000000002"
BEACON = "0x0000000000000000000000000000000000000003"


def _stub_chain(monkeypatch, *, slot=None, clone=None, beacon=None) -> None:
    monkeypatch.setattr("scanner.proxy.read_eip1967_implementation", lambda *a, **k: slot)
    monkeypatch.setattr("scanner.proxy.read_eip1167_implementation", lambda *a, **k: clone)
    monkeypatch.setattr("scanner.proxy.read_beacon_implementation", lambda *a, **k: beacon)


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
    _stub_chain(monkeypatch)

    def fake_fetch(address: str, api_key=None, chain_id=None):
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
    _stub_chain(monkeypatch)

    def fake_fetch(address: str, api_key=None, chain_id=None):
        if address.lower() == PROXY.lower():
            return _verified(PROXY, "Proxy", is_proxy=True, implementation=IMPL)
        raise SourceNotVerifiedError("impl not verified")

    monkeypatch.setattr("scanner.proxy.fetch_verified_source", fake_fetch)
    target = fetch_scan_target(PROXY)
    assert target.source_role == "proxy_fallback"
    assert target.analyzed.name == "Proxy"
    assert target.note and "not verified" in target.note.lower()


def test_no_follow_without_implementation(monkeypatch) -> None:
    _stub_chain(monkeypatch)
    monkeypatch.setattr(
        "scanner.proxy.fetch_verified_source",
        lambda address, api_key=None, chain_id=None: _verified(address, "Plain"),
    )
    target = fetch_scan_target(PROXY)
    assert target.source_role == "declared"
    assert target.implementation is None


def test_eip1967_used_when_explorer_omits_impl(monkeypatch) -> None:
    _stub_chain(monkeypatch, slot=IMPL)

    def fake_fetch(address: str, api_key=None, chain_id=None):
        if address.lower() == PROXY.lower():
            return _verified(PROXY, "Proxy", is_proxy=True, implementation=None)
        return _verified(IMPL, "Logic")

    monkeypatch.setattr("scanner.proxy.fetch_verified_source", fake_fetch)
    target = fetch_scan_target(PROXY)
    assert target.source_role == "implementation"
    assert target.implementation.lower() == IMPL.lower()


def test_resolve_ignores_self_implementation(monkeypatch) -> None:
    _stub_chain(monkeypatch)
    verified = _verified(PROXY, "Proxy", is_proxy=True, implementation=PROXY)
    assert resolve_implementation_address(verified, PROXY) is None


def test_parse_eip1167_runtime() -> None:
    impl = bytes.fromhex(IMPL[2:].zfill(40))
    code = bytes.fromhex("363d3d373d3d3d363d73") + impl + bytes.fromhex("5af43d82803e903d91602b57fd5bf3")
    assert parse_eip1167_implementation(code).lower() == IMPL.lower()
    assert parse_eip1167_implementation(b"") is None
    assert parse_eip1167_implementation(b"\x00" * 50) is None


def test_follows_minimal_proxy_bytecode(monkeypatch) -> None:
    _stub_chain(monkeypatch, clone=IMPL)

    def fake_fetch(address: str, api_key=None, chain_id=None):
        if address.lower() == PROXY.lower():
            return _verified(PROXY, "Clone")
        return _verified(IMPL, "Logic")

    monkeypatch.setattr("scanner.proxy.fetch_verified_source", fake_fetch)
    target = fetch_scan_target(PROXY)
    assert target.source_role == "implementation"
    assert target.analyzed.name == "Logic"
    assert target.implementation.lower() == IMPL.lower()


def test_follows_beacon_then_logic(monkeypatch) -> None:
    def clone_or_beacon(address, rpc_url=None):
        if address.lower() == PROXY.lower():
            return BEACON
        return None

    def beacon_logic(address, rpc_url=None):
        if address.lower() == BEACON.lower():
            return IMPL
        return None

    monkeypatch.setattr("scanner.proxy.read_eip1967_implementation", lambda *a, **k: None)
    monkeypatch.setattr("scanner.proxy.read_eip1167_implementation", clone_or_beacon)
    monkeypatch.setattr("scanner.proxy.read_beacon_implementation", beacon_logic)

    def fake_fetch(address: str, api_key=None, chain_id=None):
        lowered = address.lower()
        if lowered == PROXY.lower():
            return _verified(PROXY, "Clone")
        if lowered == BEACON.lower():
            return _verified(BEACON, "BeaconProxy")
        return _verified(IMPL, "Logic")

    monkeypatch.setattr("scanner.proxy.fetch_verified_source", fake_fetch)
    target = fetch_scan_target(PROXY)
    assert target.source_role == "implementation"
    assert target.analyzed.name == "Logic"
    assert target.implementation.lower() == IMPL.lower()
