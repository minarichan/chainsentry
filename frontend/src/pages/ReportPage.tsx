import { useState } from "react";
import { FindingCard } from "../components/FindingCard";
import { FunctionTable } from "../components/FunctionTable";
import { ScanSummary } from "../components/ScanSummary";
import { Overview } from "../components/ScoreGauge";
import { downloadScanExport, setFindingMute } from "../services/api";
import type { Finding, ScanResult } from "../types/scan";

function formatCompilerErrors(errors: string[]) {
  const text = errors.join("\n\n");
  if (text.length <= 2500) return text;
  return `${text.slice(0, 2500)}\n… (truncated)`;
}

function compilerLogBody(errors: string[]) {
  const rest = errors.filter((item) => !item.startsWith("This source imports"));
  return formatCompilerErrors(rest.length ? rest : errors.slice(1));
}

function uniqueFindings(findings: Finding[]): Finding[] {
  const seen = new Map<string, Finding>();
  for (const finding of findings) {
    const key = `${finding.id}|${finding.function ?? ""}|${finding.location.line}|${finding.description}`;
    const existing = seen.get(key);
    if (!existing) {
      seen.set(key, finding);
      continue;
    }
    const names = [existing.contract, finding.contract].filter(Boolean);
    const merged = [...new Set(names)];
    const next = existing;
    if (merged.length) {
      seen.set(key, {
        ...next,
        contract: merged.join(", "),
        muted: Boolean(existing.muted || finding.muted),
      });
    } else if (finding.muted) {
      seen.set(key, { ...existing, muted: true });
    }
  }
  return [...seen.values()];
}

export function ReportPage({
  result,
  onReset,
  onResult,
}: {
  result: ScanResult;
  onReset: () => void;
  onResult?: (result: ScanResult) => void;
}) {
  const [tab, setTab] = useState<"overview" | "findings" | "functions" | "onchain">("overview");
  const [exportError, setExportError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const findings = uniqueFindings(result.findings);
  const active = findings.filter((finding) => !finding.muted);
  const compilerDump = compilerLogBody(result.compiler_errors);

  async function onExport(kind: "markdown" | "sarif") {
    setExportError(null);
    try {
      await downloadScanExport(result.id, kind);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    }
  }

  async function onMute(finding: Finding, muted: boolean) {
    setExportError(null);
    try {
      const next = await setFindingMute(result.id, finding, muted);
      onResult?.(next);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Could not update finding");
    }
  }

  async function copyLink() {
    const url = `${window.location.origin}${window.location.pathname}#/report/${result.id}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setExportError("Could not copy link");
    }
  }

  return (
    <>
      <div className="meta-row">
        <div>
          <p className="kicker" style={{ marginBottom: 6 }}>
            Scan complete
          </p>
          <h1 style={{ fontSize: "clamp(32px, 4vw, 48px)" }}>Security report</h1>
        </div>
        <div className="meta-actions">
          <button className="btn ghost small" type="button" onClick={() => void copyLink()}>
            {copied ? "Copied" : "Copy link"}
          </button>
          <button className="btn ghost small" type="button" onClick={() => void onExport("markdown")}>
            Markdown
          </button>
          <button className="btn ghost small" type="button" onClick={() => void onExport("sarif")}>
            SARIF
          </button>
          <button className="btn ghost" type="button" onClick={onReset}>
            New scan
          </button>
        </div>
      </div>
      {exportError ? <p className="stop">{exportError}</p> : null}

      <div className="panel">
        <Overview result={result} findings={active} />
      </div>

      <div className="panel">
        <div className="tabs">
          <button type="button" className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>
            Overview
          </button>
          <button type="button" className={tab === "findings" ? "active" : ""} onClick={() => setTab("findings")}>
            Findings ({findings.length})
          </button>
          <button type="button" className={tab === "functions" ? "active" : ""} onClick={() => setTab("functions")}>
            Functions
          </button>
          <button type="button" className={tab === "onchain" ? "active" : ""} onClick={() => setTab("onchain")}>
            On-chain
          </button>
        </div>

        {tab === "overview" && (
          <div>
            <ScanSummary result={result} findings={active} onOpenOnchain={() => setTab("onchain")} />
            {compilerDump.trim() ? (
              <details className="compiler-log">
                <summary>Compiler output</summary>
                <pre className="error">{compilerDump}</pre>
              </details>
            ) : null}
          </div>
        )}

        {tab === "findings" &&
          (findings.length ? (
            <div className="findings-list">
              {findings.map((finding) => (
                <FindingCard
                  key={`${finding.id}-${finding.contract}-${finding.location.file}-${finding.location.line}-${finding.function}`}
                  finding={finding}
                  onMute={(item, muted) => void onMute(item, muted)}
                />
              ))}
            </div>
          ) : (
            <p className="muted">No issues detected by the current detector set.</p>
          ))}

        {tab === "functions" && <FunctionTable surfaces={result.functions} />}

        {tab === "onchain" && (
          <div>
            {result.onchain ? (
              <>
                <p className="mono address-line">{result.onchain.address}</p>
                <p className="muted">{result.onchain.network}</p>
                <ul>
                  <li>Verified: {result.onchain.verified ? "yes" : "no"}</li>
                  <li>Transactions: {result.onchain.transaction_count ?? "n/a"}</li>
                  <li>Unique users: {result.onchain.unique_users ?? "n/a"}</li>
                  <li>ETH balance: {result.onchain.eth_balance ?? "n/a"}</li>
                  <li>Owner: {result.onchain.owner ?? "n/a"}</li>
                  <li>Proxy: {result.onchain.is_proxy ? "yes" : "no"}</li>
                  <li>Implementation: {result.onchain.implementation ?? result.implementation_address ?? "n/a"}</li>
                </ul>
                <h3>Signals</h3>
                <ul>
                  {result.onchain.signals.length
                    ? result.onchain.signals.map((s) => <li key={s}>{s}</li>)
                    : <li className="muted">None</li>}
                </ul>
              </>
            ) : (
              <p className="muted">On-chain analysis is available when you scan a verified address.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
