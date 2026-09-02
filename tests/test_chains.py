from scanner.chains import UnsupportedChainError, resolve_chain


def test_resolve_known_chains() -> None:
    eth = resolve_chain(1)
    assert eth.network == "Ethereum Mainnet"
    assert "eth.blockscout.com" in eth.blockscout_contract_url("0xabc")

    base = resolve_chain(8453)
    assert base.label == "Base"
    assert "base.blockscout.com" in base.blockscout_contract_url("0xabc")
    assert base.rpc_url() == "https://mainnet.base.org"

    arb = resolve_chain(42161)
    assert arb.network == "Arbitrum One"
    assert "arbitrum.blockscout.com" in arb.blockscout_contract_url("0xabc")


def test_resolve_rejects_unknown_chain() -> None:
    try:
        resolve_chain(10)
        raise AssertionError("expected UnsupportedChainError")
    except UnsupportedChainError as exc:
        assert "8453" in str(exc)


def test_env_default_ignored_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_CHAIN_ID", "1")
    assert resolve_chain(8453).id == 8453


def test_custom_blockscout_only_for_ethereum(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKSCOUT_API_URL", "https://custom.example/api/v2/smart-contracts")
    assert resolve_chain(1).blockscout_contract_url("0x1").startswith("https://custom.example/")
    assert "base.blockscout.com" in resolve_chain(8453).blockscout_contract_url("0x1")
