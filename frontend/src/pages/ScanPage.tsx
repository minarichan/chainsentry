import { useEffect, useState, type FormEvent } from "react";
import { readStoredChainId, SCAN_CHAINS, storeChainId, type ScanChainId } from "../data/chains";
import { scanAddress, scanSource } from "../services/api";
import type { ScanResult } from "../types/scan";

const SAMPLE = `pragma solidity ^0.8.0;

contract Reentrancy {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() public {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "empty");
        (bool sent, ) = msg.sender.call{value: amount}("");
        require(sent, "failed");
        balances[msg.sender] = 0;
    }
}
`;

const SCAN_STEPS = [
  "Fetching verified source…",
  "Downloading solc if needed, then compiling…",
  "Running detectors…",
];

interface Props {
  onResult: (result: ScanResult) => void;
  loadError?: string | null;
}

function focusAddress() {
  document.getElementById("scan-panel")?.scrollIntoView({ behavior: "smooth" });
  document.getElementById("contract-address")?.focus();
}

export function ScanPage({ onResult, loadError }: Props) {
  const [address, setAddress] = useState("");
  const [chainId, setChainId] = useState<ScanChainId>(readStoredChainId);
  const [source, setSource] = useState(SAMPLE);
  const [showSource, setShowSource] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!busy) {
      setStep(0);
      return;
    }
    const id = window.setInterval(() => {
      setStep((current) => (current + 1) % SCAN_STEPS.length);
    }, 4000);
    return () => window.clearInterval(id);
  }, [busy]);

  async function run(task: () => Promise<ScanResult>) {
    setBusy(true);
    setError(null);
    try {
      onResult(await task());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  function onAddressSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = address.trim();
    if (!trimmed) {
      setError("Provide a contract address.");
      return;
    }
    void run(() => scanAddress(trimmed, chainId));
  }

  function onSourceSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = source.trim();
    if (!trimmed) {
      setError("Provide Solidity source.");
      return;
    }
    void run(() => scanSource(trimmed, "Contract.sol"));
  }

  return (
    <>
      <section className="hero-grid">
        <div>
          <p className="kicker">Static analysis for Solidity</p>
          <h1>Security scanner for the on-chain stack</h1>
          <p className="lede">
            Paste a verified contract address on Ethereum, Base, or Arbitrum.
            ChainSentry fetches the source, compiles it, and reports reentrancy,
            access control, and other SWC issues.
          </p>
          <button className="btn" type="button" onClick={focusAddress}>
            Scan a contract
          </button>
        </div>
      </section>

      <form className="scan-bar" id="scan-panel" onSubmit={onAddressSubmit}>
        <label className="scan-bar-label" htmlFor="scan-chain">
          Chain
        </label>
        <select
          id="scan-chain"
          className="scan-bar-chain"
          value={chainId}
          onChange={(e) => {
            const next = Number(e.target.value);
            const chain = SCAN_CHAINS.find((item) => item.id === next);
            if (!chain) return;
            setChainId(chain.id);
            storeChainId(chain.id);
          }}
        >
          {SCAN_CHAINS.map((chain) => (
            <option key={chain.id} value={chain.id}>
              {chain.label}
            </option>
          ))}
        </select>
        <span className="scan-bar-split" aria-hidden="true" />
        <label className="scan-bar-label" htmlFor="contract-address">
          Contract address
        </label>
        <input
          id="contract-address"
          type="text"
          className="mono"
          placeholder="0x…"
          autoComplete="off"
          spellCheck={false}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
        />
        <button className="btn" disabled={busy} type="submit">
          {busy && !showSource ? "Scanning…" : "Scan"}
        </button>
      </form>
      <p className="scan-hint">
        Uses Sourcify, then Etherscan (needs a key in .env), then Blockscout — on the chain you pick.
      </p>
      {busy ? <p className="scan-progress">{SCAN_STEPS[step]}</p> : null}

      {error || loadError ? <p className="stop">{error || loadError}</p> : null}

      <p>
        <button
          className="btn-text"
          type="button"
          onClick={() => {
            setShowSource((open) => !open);
            setError(null);
          }}
        >
          {showSource ? "Hide Solidity source" : "Have a .sol file instead?"}
        </button>
      </p>

      {showSource ? (
        <form className="panel" onSubmit={onSourceSubmit}>
          <div className="panel-head">
            <h2>Paste source</h2>
            <span className="muted">Local files are not fetched from chain</span>
          </div>
          <label>
            Solidity source
            <textarea value={source} onChange={(e) => setSource(e.target.value)} spellCheck={false} />
          </label>
          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn" disabled={busy} type="submit">
              {busy ? "Scanning…" : "Scan source"}
            </button>
          </div>
        </form>
      ) : null}
    </>
  );
}
