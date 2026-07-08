'use client';

import { DISTRICTS } from '@/lib/districts';
import { SEVERITY_LABELS, mm } from '@/lib/format';
import type { RainPoint, RiskScore } from '@/lib/types';

/**
 * A2 — "map data as text": a visually-hidden table exposing the choropleth to
 * screen readers and assistive tech, since a WebGL canvas is otherwise opaque
 * to them. Kept in sync with the same feeds the map draws from.
 */
export default function MapDataTable({
  risk,
  rain,
}: {
  risk: RiskScore[] | null;
  rain: RainPoint[] | null;
}) {
  const riskById = new Map((risk ?? []).map((r) => [r.districtId, r]));
  const rainById = new Map((rain ?? []).map((r) => [r.districtId, r]));

  return (
    <section className="sr-only" aria-label="District risk data (text alternative to the map)">
      <h2>District risk and rainfall</h2>
      <table>
        <caption>Composite risk index and forecast rainfall by district</caption>
        <thead>
          <tr>
            <th scope="col">District</th>
            <th scope="col">Risk level</th>
            <th scope="col">Risk score (0–100)</th>
            <th scope="col">Rain next 24 h</th>
          </tr>
        </thead>
        <tbody>
          {DISTRICTS.map((d) => {
            const r = riskById.get(d.id);
            const rf = rainById.get(d.id);
            return (
              <tr key={d.id}>
                <th scope="row">{d.name}</th>
                <td>{r ? SEVERITY_LABELS[r.severity] : 'No data'}</td>
                <td>{r ? r.score : '—'}</td>
                <td>{rf ? mm(rf.next24h) : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
