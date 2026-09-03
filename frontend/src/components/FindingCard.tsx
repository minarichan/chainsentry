import type { Finding } from "../types/scan";

const COLORS: Record<string, string> = {
  critical: "#7a1f1f",
  high: "#c23b32",
  medium: "#c47a2c",
  low: "#9a7b24",
  info: "#3d5f8a",
};

export function FindingCard({
  finding,
  onMute,
}: {
  finding: Finding;
  onMute?: (finding: Finding, muted: boolean) => void;
}) {
  const start = finding.snippet_start_line || finding.location.line;
  const lines = finding.snippet ? finding.snippet.split("\n") : [];
  const file = finding.location.file;
  const muted = Boolean(finding.muted);

  return (
    <article className={`finding${muted ? " is-muted" : ""}`}>
      <header>
        <span className="sev" style={{ background: COLORS[finding.severity] }}>
          {finding.severity.toUpperCase()}
        </span>
        <span className="mono muted">{finding.id}</span>
        <span className="mono muted">{finding.classification}</span>
        {muted ? <span className="mute-tag">Not an issue</span> : null}
        {onMute ? (
          <button
            className="btn-text finding-mute"
            type="button"
            onClick={() => onMute(finding, !muted)}
          >
            {muted ? "Restore" : "Not an issue"}
          </button>
        ) : null}
      </header>
      <h3>{finding.title}</h3>
      <p className="muted">
        {[
          finding.contract,
          file,
          finding.function ?? "—",
          `Line ${finding.location.line}`,
          `Confidence ${finding.confidence}%`,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <p>{finding.description}</p>
      {lines.length ? (
        <pre className="snippet" tabIndex={0}>
          {lines.map((text, index) => {
            const number = start + index;
            const hit = number === finding.location.line;
            return (
              <div className={hit ? "snip-line hit" : "snip-line"} key={`${number}-${index}`}>
                <span className="n">{number}</span>
                <code>{text || " "}</code>
              </div>
            );
          })}
        </pre>
      ) : null}
      <p className="muted">
        <strong>Recommendation.</strong> {finding.recommendation}
      </p>
    </article>
  );
}
