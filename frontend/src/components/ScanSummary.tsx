import { DETECTORS } from "../data/detectors";
import { SeverityDot } from "./ScoreGauge";
import type { Finding, ScanResult } from "../types/scan";

const ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

function shortAddress(value: string) {
  if (value.length < 14) return value;
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function headlineContract(result: ScanResult) {
  const impl = result.contracts.find((c) => c.kind === "contract");
  return impl?.name || result.contracts[0]?.name || result.filename;
}

export function verdictLine(result: ScanResult, findings: Finding[]): string {
  if (result.compiler_errors.length) {
    return "Compilation failed. Detectors did not run on this source.";
  }
  if (!findings.length) {
    return "No issues from the current detector set.";
  }
  const ranked = [...findings].sort(
    (a, b) => (ORDER[a.severity] ?? 9) - (ORDER[b.severity] ?? 9),
  );
  const top = ranked[0];
  const highish = findings.filter((f) => f.severity === "critical" || f.severity === "high").length;
  const medium = findings.filter((f) => f.severity === "medium").length;
  const where = top.function ? ` in \`${top.function}\`` : "";
  if (highish) {
    return `${highish} high-severity issue${highish === 1 ? "" : "s"}. Top hit: ${top.title}${where}.`;
  }
  if (medium) {
    return `No high issues. ${medium} medium finding${medium === 1 ? "" : "s"}, starting with ${top.title}${where}.`;
  }
  return `No high or medium issues. ${findings.length} low/info note${findings.length === 1 ? "" : "s"}.`;
}

export function ScanSummary({
  result,
  findings,
  onOpenOnchain,
}: {
  result: ScanResult;
  findings: Finding[];
  onOpenOnchain: () => void;
}) {
  const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const finding of findings) {
    counts[finding.severity] += 1;
  }
  const byDetector = new Map<string, number>(DETECTORS.map((d) => [d.id, 0]));
  for (const finding of findings) {
    byDetector.set(finding.id, (byDetector.get(finding.id) ?? 0) + 1);
  }

  const implNames = result.contracts.filter((c) => c.kind === "contract").map((c) => c.name);
  const shown = (implNames.length ? implNames : result.contracts.map((c) => c.name)).slice(0, 6);
  const extra = Math.max(0, result.contracts.length - shown.length);
  const files = new Set(
    [result.filename, ...findings.map((f) => f.location.file).filter(Boolean)].filter(Boolean),
  );
  const riskyFns = result.functions.filter((fn) => fn.risk === "HIGH").length;
  const chain = result.onchain;

  return (
    <div className="summary">
      <p className="summary-verdict">{verdictLine(result, findings)}</p>

      <div className="summary-grid">
        <section>
          <h3>Severity mix</h3>
          <ul className="summary-stats">
            <li>
              <SeverityDot severity="high" /> High {counts.high + counts.critical}
            </li>
            <li>
              <SeverityDot severity="medium" /> Medium {counts.medium}
            </li>
            <li>
              <SeverityDot severity="low" /> Low {counts.low}
            </li>
            <li>
              <SeverityDot severity="info" /> Info {counts.info}
            </li>
          </ul>
        </section>

        <section>
          <h3>Analyzed</h3>
          <ul className="summary-facts">
            <li>
              <span>Target</span>
              <strong>{headlineContract(result)}</strong>
            </li>
            {result.source_role === "implementation" && result.implementation_address ? (
              <li>
                <span>Source</span>
                <strong>implementation behind proxy</strong>
              </li>
            ) : null}
            {result.implementation_address ? (
              <li>
                <span>Implementation</span>
                <strong className="mono">{shortAddress(result.implementation_address)}</strong>
              </li>
            ) : null}
            <li>
              <span>Compiler</span>
              <strong>solc {result.solc_version || "n/a"}</strong>
            </li>
            <li>
              <span>Contracts</span>
              <strong>{result.contracts.length}</strong>
            </li>
            <li>
              <span>Source files</span>
              <strong>{files.size || 1}</strong>
            </li>
            <li>
              <span>Functions mapped</span>
              <strong>{result.functions.length}</strong>
            </li>
            <li>
              <span>High-risk functions</span>
              <strong>{riskyFns}</strong>
            </li>
          </ul>
          {shown.length ? (
            <p className="muted summary-names">
              {shown.join(", ")}
              {extra ? ` + ${extra} more` : ""}
            </p>
          ) : null}
        </section>
      </div>

      <section>
        <h3>Detector mix</h3>
        <div className="summary-detectors">
          {DETECTORS.map((detector) => {
            const n = byDetector.get(detector.id) ?? 0;
            return (
              <div className={`summary-chip ${n ? "hit" : ""}`} key={detector.id}>
                <span>{detector.title}</span>
                <strong>{n}</strong>
              </div>
            );
          })}
        </div>
      </section>

      {chain ? (
        <section className="summary-chain">
          <h3>On-chain snapshot</h3>
          <ul className="summary-facts">
            <li>
              <span>Address</span>
              <strong className="mono">{shortAddress(chain.address)}</strong>
            </li>
            <li>
              <span>Verified source</span>
              <strong>{chain.verified ? "yes" : "no"}</strong>
            </li>
            <li>
              <span>Proxy</span>
              <strong>{chain.is_proxy ? "yes" : "no"}</strong>
            </li>
            {chain.implementation ? (
              <li>
                <span>Implementation</span>
                <strong className="mono">{shortAddress(chain.implementation)}</strong>
              </li>
            ) : null}
            <li>
              <span>Owner</span>
              <strong className="mono">
                {chain.owner ? shortAddress(chain.owner) : "n/a"}
              </strong>
            </li>
            <li>
              <span>Balance</span>
              <strong>{chain.eth_balance ?? "n/a"}</strong>
            </li>
          </ul>
          {chain.signals.length ? (
            <p className="muted">{chain.signals.join(" · ")}</p>
          ) : null}
          <button className="btn-text" type="button" onClick={onOpenOnchain}>
            See on-chain details
          </button>
        </section>
      ) : result.address ? (
        <p className="muted">On-chain stats were skipped for this scan.</p>
      ) : null}
    </div>
  );
}
