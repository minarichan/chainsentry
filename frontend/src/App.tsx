import { useEffect, useState } from "react";
import { EthMark } from "./components/EthMark";
import { DetectorsPage } from "./pages/DetectorsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ReportPage } from "./pages/ReportPage";
import { ScanPage } from "./pages/ScanPage";
import { SettingsPage } from "./pages/SettingsPage";
import { forgetScan, rememberScan } from "./data/history";
import { getScan } from "./services/api";
import type { ScanResult } from "./types/scan";

type View = "scan" | "report" | "detectors" | "history" | "settings";

const NAV: { view: View; href: string; label: string }[] = [
  { view: "scan", href: "#/", label: "Scan" },
  { view: "report", href: "#/report", label: "Report" },
  { view: "history", href: "#/history", label: "History" },
  { view: "detectors", href: "#/detectors", label: "Detectors" },
  { view: "settings", href: "#/settings", label: "Settings" },
];

function parseHash(): { view: View; id: string | null } {
  const path = window.location.hash.replace(/^#\/?/, "");
  if (path === "detectors") return { view: "detectors", id: null };
  if (path === "history") return { view: "history", id: null };
  if (path === "settings") return { view: "settings", id: null };
  if (path === "report" || path.startsWith("report/")) {
    const id = path === "report" ? "" : path.slice("report/".length).split(/[/?#]/)[0];
    return { view: "report", id: id || null };
  }
  return { view: "scan", id: null };
}

export default function App() {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [view, setView] = useState<View>(() => parseHash().view);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  useEffect(() => {
    function onHash() {
      const next = parseHash();
      setView(next.view);
      if (next.view === "report" && next.id && next.id !== result?.id) {
        const scanId = next.id;
        setLoadingReport(true);
        setLoadError(null);
        void getScan(scanId)
          .then((payload: ScanResult) => {
            setResult(payload);
            setView("report");
          })
          .catch(() => {
            forgetScan(scanId);
            setResult(null);
            setLoadError(
              "That report is gone. This demo does not keep scans across deploys — run a new one.",
            );
            setView("scan");
            if (window.location.hash.startsWith("#/report/")) {
              window.location.hash = "#/";
            }
          })
          .finally(() => setLoadingReport(false));
      }
    }
    window.addEventListener("hashchange", onHash);
    onHash();
    return () => window.removeEventListener("hashchange", onHash);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function showScan() {
    setResult(null);
    setLoadError(null);
    setView("scan");
    window.location.hash = "#/";
  }

  const reportHref = result ? `#/report/${result.id}` : "#/report";

  return (
    <div className="page">
      <div className="stage">
        <header className="nav">
          <a className="logo" href="#/" aria-label="ChainSentry home">
            <EthMark />
            ChainSentry
          </a>
          <nav className="nav-links" aria-label="Main">
            {NAV.map((item) => {
              const href = item.view === "report" ? reportHref : item.href;
              const active = view === item.view;
              if (active) {
                return (
                  <span key={item.view} className="nav-link active" aria-current="page">
                    {item.label}
                  </span>
                );
              }
              return (
                <a key={item.view} className="nav-link" href={href}>
                  {item.label}
                </a>
              );
            })}
          </nav>
          <a
            className="nav-github"
            href="https://github.com/minarichan/chainsentry"
            target="_blank"
            rel="noreferrer"
            aria-label="GitHub"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.17-3.37-1.17-.45-1.15-1.1-1.46-1.1-1.46-.9-.62.07-.6.07-.6 1 .07 1.52 1.03 1.52 1.03.89 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.95 0-1.1.39-1.99 1.03-2.7-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.03a9.56 9.56 0 0 1 5 0c1.91-1.3 2.75-1.03 2.75-1.03.55 1.37.2 2.39.1 2.64.64.71 1.03 1.6 1.03 2.7 0 3.85-2.34 4.7-4.57 4.95.36.31.68.92.68 1.86v2.76c0 .26.18.58.69.48A10 10 0 0 0 12 2z"
              />
            </svg>
          </a>
        </header>

        <main className="shell">
          {loadingReport ? (
            <p className="muted">Loading report…</p>
          ) : view === "history" ? (
            <HistoryPage />
          ) : view === "settings" ? (
            <SettingsPage />
          ) : view === "detectors" ? (
            <DetectorsPage />
          ) : view === "report" && result ? (
            <ReportPage result={result} onReset={showScan} onResult={setResult} />
          ) : view === "report" ? (
            <>
              <p className="kicker">No scan yet</p>
              <h1>Security report</h1>
              <p className="lede">
                Run a scan first. After it finishes, this page holds the findings and a
                shareable link.
              </p>
              <p>
                <a className="btn" href="#/" onClick={showScan}>
                  Scan a contract
                </a>
              </p>
            </>
          ) : (
            <ScanPage
              loadError={loadError}
              onResult={(next) => {
                const label = next.address || next.analyzed_name || next.filename;
                rememberScan(next.id, label);
                setResult(next);
                setLoadError(null);
                setView("report");
                window.location.hash = `#/report/${next.id}`;
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
