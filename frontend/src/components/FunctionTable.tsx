import type { FunctionSurface } from "../types/scan";
import { SeverityDot } from "./ScoreGauge";

export function FunctionTable({ surfaces }: { surfaces: FunctionSurface[] }) {
  return (
    <table className="stack">
      <thead>
        <tr>
          <th>Function</th>
          <th>Visibility</th>
          <th>Mutability</th>
          <th>Risk</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {surfaces.map((fn) => (
          <tr key={`${fn.contract}.${fn.name}.${fn.line}`}>
            <td data-label="Function">
              <code>
                {fn.name}()
              </code>
            </td>
            <td data-label="Visibility">{fn.visibility}</td>
            <td data-label="Mutability">{fn.mutability}</td>
            <td data-label="Risk">
              <span className="pill">
                <SeverityDot severity={fn.risk} /> {fn.risk}
              </span>
            </td>
            <td data-label="Notes">
              <ul className="flags">
                {fn.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
