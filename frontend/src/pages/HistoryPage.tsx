import { readScanHistory } from "../data/history";

function formatWhen(at: number) {
  try {
    return new Date(at).toLocaleString();
  } catch {
    return "";
  }
}

export function HistoryPage() {
  const items = readScanHistory();

  return (
    <>
      <p className="kicker">This browser</p>
      <h1>History</h1>
      <p className="lede">
        Reports you finish here are kept on this device for 14 days. They are not
        a shared account list.
      </p>
      {items.length ? (
        <div className="panel">
          <div className="panel-head">
            <h2>Recent scans</h2>
            <span className="muted">{items.length}</span>
          </div>
          <ul className="history-list">
            {items.map((item) => (
              <li key={item.id}>
                <a href={`#/report/${item.id}`}>{item.label}</a>
                <span className="muted">{formatWhen(item.at)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="panel">
          <p className="muted" style={{ margin: 0 }}>
            No scans yet.{" "}
            <a className="btn-text" href="#/">
              Scan a contract
            </a>
          </p>
        </div>
      )}
    </>
  );
}
