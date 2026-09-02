import type { Finding, ScanResult } from "../types/scan";

export function SeverityDot({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    critical: "#7a1f1f",
    high: "#c23b32",
    medium: "#c47a2c",
    low: "#9a7b24",
    info: "#3d5f8a",
    HIGH: "#c23b32",
    MEDIUM: "#c47a2c",
    LOW: "#2f7a57",
  };
  return <span className="dot" style={{ background: map[severity] ?? "#6b6b6b" }} />;
}

function hitsLabel(n: number) {
  return n === 1 ? "1 hit" : `${n} hits`;
}

export function Overview({ result, findings }: { result: ScanResult; findings?: Finding[] }) {
  const impl = result.contracts.find((c) => c.kind === "contract");
  const name = impl?.name || result.contracts[0]?.name || result.filename;
  const others = Math.max(0, result.contracts.length - 1);
  const list = findings ?? result.findings;
  const high = list.filter((f) => f.severity === "high" || f.severity === "critical").length;
  const medium = list.filter((f) => f.severity === "medium").length;
  const low = list.filter((f) => f.severity === "low").length;
  const info = list.filter((f) => f.severity === "info").length;
  const verdict = result.verdict_label || result.scorecard?.verdict_label || "Scan complete";
  const tone = result.verdict || result.scorecard?.verdict || "clean";

  return (
    <div className="score-block">
      <div className={`score-num verdict-${tone}`}>
        {verdict}
        <span>Heuristic AST scan. Severity mix is the report — not a calibrated score.</span>
      </div>
      <div>
        <h2 className="score-name">{name}</h2>
        <p className="muted">
          {result.address
            ? `${result.network} · Verified on-chain source`
            : `${result.network} · ${result.filename}`}
          {result.solc_version ? ` · solc ${result.solc_version}` : ""}
          {others ? ` · ${result.contracts.length} types` : ""}
        </p>
        {result.address ? <p className="mono muted address-line">{result.address}</p> : null}
        {result.source_role === "implementation" && result.implementation_address ? (
          <p className="muted">
            Analyzed implementation{" "}
            <span className="mono address-line">{result.implementation_address}</span>
            {result.analyzed_name ? ` (${result.analyzed_name})` : ""} behind this proxy.
          </p>
        ) : null}
        {result.source_role === "proxy_fallback" && result.proxy_note ? (
          <p className="muted">{result.proxy_note}</p>
        ) : null}
        <div className="counts">
          <span className="pill">
            <SeverityDot severity="high" /> {high} High
          </span>
          <span className="pill">
            <SeverityDot severity="medium" /> {medium} Medium
          </span>
          <span className="pill">
            <SeverityDot severity="low" /> {low} Low
          </span>
          <span className="pill">
            <SeverityDot severity="info" /> {info} Info
          </span>
        </div>
        <div className="cats">
          {(result.scorecard?.categories ?? []).map((cat) => (
            <div className="cat" key={cat.name}>
              <span>{cat.name}</span>
              <strong>{hitsLabel(cat.finding_count)}</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
