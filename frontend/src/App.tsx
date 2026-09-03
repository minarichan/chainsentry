import { useEffect, useState } from "react";
import { EthMark } from "./components/EthMark";
import { DetectorsPage } from "./pages/DetectorsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ReportPage } from "./pages/ReportPage";
import { ScanPage } from "./pages/ScanPage";
import { forgetScan, rememberScan } from "./data/history";
import { getScan } from "./services/api";
import type { ScanResult } from "./types/scan";

type View = "scan" | "report" | "detectors" | "history";

function parseHash(): { view: View; id: string | null } {
  const path = window.location.hash.replace(/^#\/?/, "");
  if (path === "detectors") return { view: "detectors", id: null };
  if (path === "history") return { view: "history", id: null };
  if (path === "report" || path.startsWith("report/")) {
    const id = path === "report" ? "" : path.slice("report/".length).split(/[/?#]/)[0];
    if (id) return { view: "report", id };
    return { view: "scan", id: null };
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
        setLoadingReport(true);
        setLoadError(null);
        void getScan(next.id)
          .then((payload: ScanResult) => {
            setResult(payload);
            setView("report");
          })
          .catch(() => {
            forgetScan(next.id);
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
    // Only run on mount; later hash changes still fire the listener.
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
          <div className="nav-pill">
            {view === "scan" ? (
              <span className="nav-link active" aria-current="page">
                Scan
              </span>
            ) : (
              <a className="nav-link" href="#/">
                Scan
              </a>
            )}
            <a
              className={`nav-link ${view === "report" ? "active" : ""} ${result ? "" : "is-disabled"}`}
              href={reportHref}
              aria-disabled={!result}
              onClick={(event) => {
                if (!result) event.preventDefault();
              }}
            >
              Report
            </a>
            {view === "history" ? (
              <span className="nav-link active" aria-current="page">
                History
              </span>
            ) : (
              <a className="nav-link" href="#/history">
                History
              </a>
            )}
            <a
              className={`nav-link ${view === "detectors" ? "active" : ""}`}
              href="#/detectors"
            >
              Detectors
            </a>
          </div>
        </header>

        <main className="shell">
          {loadingReport ? (
            <p className="muted">Loading report…</p>
          ) : view === "history" ? (
            <HistoryPage />
          ) : view === "detectors" ? (
            <DetectorsPage />
          ) : view === "report" && result ? (
            <ReportPage result={result} onReset={showScan} onResult={setResult} />
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
