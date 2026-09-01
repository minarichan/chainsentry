import { useState } from "react";
import { EthMark } from "./components/EthMark";
import { DetectorsPage } from "./pages/DetectorsPage";
import { ReportPage } from "./pages/ReportPage";
import { ScanPage } from "./pages/ScanPage";
import type { ScanResult } from "./types/scan";

type View = "scan" | "report" | "detectors";

export default function App() {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [view, setView] = useState<View>("scan");

  function showScan() {
    setResult(null);
    setView("scan");
  }

  return (
    <div className="page">
      <div className="stage">
        <header className="nav">
          <button type="button" className="logo" onClick={showScan}>
            <EthMark />
            ChainSentry
          </button>
          <div className="nav-pill">
            <button
              type="button"
              className={`nav-link ${view === "scan" ? "active" : ""}`}
              onClick={showScan}
            >
              Scan
            </button>
            <button
              type="button"
              className={`nav-link ${view === "report" ? "active" : ""}`}
              disabled={!result}
              onClick={() => result && setView("report")}
            >
              Report
            </button>
            <button
              type="button"
              className={`nav-link ${view === "detectors" ? "active" : ""}`}
              onClick={() => setView("detectors")}
            >
              Detectors
            </button>
            {result && view !== "scan" ? (
              <button className="btn small" type="button" onClick={showScan}>
                New scan
              </button>
            ) : (
              <button
                className="btn small"
                type="button"
                onClick={() => {
                  setView("scan");
                  document.getElementById("scan-panel")?.scrollIntoView({ behavior: "smooth" });
                  document.getElementById("contract-address")?.focus();
                }}
              >
                Scan contract
              </button>
            )}
          </div>
        </header>

        <main className="shell">
          {view === "detectors" ? (
            <DetectorsPage />
          ) : view === "report" && result ? (
            <ReportPage result={result} onReset={showScan} />
          ) : (
            <ScanPage
              onResult={(next) => {
                setResult(next);
                setView("report");
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
