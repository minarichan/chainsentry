import { DETECTORS } from "../data/detectors";

export function DetectorsPage() {
  return (
    <>
      <p className="kicker">Static analysis</p>
      <h1>Detectors</h1>
      <p className="lede">
        Findings are grouped by severity. There is no calibrated 0–100 rating.
        Unverified bytecode is not analyzed.
      </p>
      <div className="panel">
        <div className="panel-head">
          <h2>Built-in checks</h2>
          <span className="muted">{DETECTORS.length} detectors</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Detector</th>
              <th>ID</th>
              <th>What it flags</th>
            </tr>
          </thead>
          <tbody>
            {DETECTORS.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.title}</strong>
                  <div className="muted">{item.swc}</div>
                </td>
                <td className="mono">{item.id}</td>
                <td>{item.summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
