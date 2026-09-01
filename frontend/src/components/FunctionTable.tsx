import type { FunctionSurface } from "../types/scan";
import { SeverityDot } from "./ScoreGauge";

export function FunctionTable({ surfaces }: { surfaces: FunctionSurface[] }) {
  return (
    <table>
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
            <td>
              <code>
                {fn.name}()
              </code>
            </td>
            <td>{fn.visibility}</td>
            <td>{fn.mutability}</td>
            <td>
              <span className="pill">
                <SeverityDot severity={fn.risk} /> {fn.risk}
              </span>
            </td>
            <td>
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
