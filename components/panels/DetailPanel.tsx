'use client';

import { DISTRICT_BY_ID } from '@/lib/districts';
import { SEVERITY_LABELS, mm } from '@/lib/format';
import { SEVERITY_COLORS } from '@/lib/types';
import type { RainPoint, RiskScore, RiverStatus } from '@/lib/types';
import { useAppStore } from '@/store/useAppStore';

interface Props {
  risk: RiskScore[] | null;
  rain: RainPoint[] | null;
  rivers: RiverStatus[] | null;
}

const RIVER_STATUS_COLOR: Record<RiverStatus['status'], string> = {
  normal: '#22c55e',
  elevated: '#f97316',
  high: '#ef4444',
};

/** District drill-down: risk ring, driver bars, 72 h rain sparkline, rivers. */
export default function DetailPanel({ risk, rain, rivers }: Props) {
  const id = useAppStore((s) => s.selectedDistrictId);
  const selectDistrict = useAppStore((s) => s.selectDistrict);
  const timelineHour = useAppStore((s) => s.timelineHour);

  if (!id) return null;
  const district = DISTRICT_BY_ID.get(id);
  if (!district) return null;

  const r = risk?.find((x) => x.districtId === id);
  const rf = rain?.find((x) => x.districtId === id);
  const districtRivers = (rivers ?? []).filter((g) => g.districtId === id);
  const color = r ? SEVERITY_COLORS[r.severity] : '#64748b';

  return (
    <aside
      aria-label={`${district.name} district details`}
      className="pointer-events-auto w-80 animate-slide-up overflow-y-auto rounded-2xl border border-white/10 bg-ink-900/80 p-4 shadow-2xl backdrop-blur-xl max-h-[70vh] md:max-h-[calc(100vh-180px)]"
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-bold text-white">{district.name}</h2>
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-400">
            {district.coastal ? 'coastal · ' : ''}
            {district.popDensity.toLocaleString('en-IN')} people/km²
          </p>
        </div>
        <button
          onClick={() => selectDistrict(null)}
          aria-label="Close district details"
          className="rounded-lg p-1.5 text-ink-400 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      </div>

      {/* Risk ring */}
      <div className="mb-4 flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.03] p-3">
        <RiskRing score={r?.score ?? 0} color={color} />
        <div>
          <p className="text-2xl font-bold" style={{ color }}>
            {r ? SEVERITY_LABELS[r.severity] : '—'}
          </p>
          <p className="text-xs text-ink-400">Composite risk index</p>
          <a href="/methodology" className="font-mono text-[10px] text-accent underline-offset-2 hover:underline">
            how is this computed?
          </a>
        </div>
      </div>

      {/* Drivers */}
      {r && (
        <div className="mb-4 space-y-1.5">
          {(
            [
              ['Rainfall', r.drivers.rain, '#38bdf8'],
              ['Landslide terrain', r.drivers.landslide, '#f59e0b'],
              ['Flood proneness', r.drivers.flood, '#818cf8'],
              ['Population exposure', r.drivers.exposure, '#f472b6'],
            ] as const
          ).map(([label, v, c]) => (
            <div key={label}>
              <div className="mb-0.5 flex justify-between text-[10px] text-ink-400">
                <span>{label}</span>
                <span className="font-mono">{Math.round(v * 100)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-ink-700" role="img" aria-label={`${label}: ${Math.round(v * 100)} of 100`}>
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${v * 100}%`, backgroundColor: c }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rain sparkline */}
      {rf && (
        <div className="mb-4 rounded-xl border border-white/5 bg-white/[0.03] p-3">
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="text-xs font-semibold text-ink-200">Rainfall — next 72 h</h3>
            <span className="font-mono text-[10px] text-ink-400">
              24h {mm(rf.next24h)} · 72h {mm(rf.next72h)}
            </span>
          </div>
          <Sparkline values={rf.hourly} marker={timelineHour} />
          <p className="mt-1.5 font-mono text-[10px] text-ink-400">past 24 h: {mm(rf.past24h)} · Open-Meteo</p>
        </div>
      )}

      {/* Rivers — live GloFAS discharge */}
      {districtRivers.length > 0 && (
        <div className="rounded-xl border border-white/5 bg-white/[0.03] p-3">
          <h3 className="mb-2 text-xs font-semibold text-ink-200">
            River discharge <span className="font-mono text-[9px] font-normal uppercase text-emerald-400">live · GloFAS</span>
          </h3>
          <ul className="space-y-1.5">
            {districtRivers.map((g) => (
              <li key={g.id} className="flex items-center justify-between gap-2 text-xs">
                <span className="min-w-0 truncate text-ink-200">
                  {g.name} <span className="text-ink-400">· {g.river}</span>
                </span>
                <span
                  className="shrink-0 font-mono"
                  style={{ color: RIVER_STATUS_COLOR[g.status] }}
                  title={`${g.ratio}× the 31-day median flow`}
                >
                  {g.dischargeM3s} m³/s {g.trend === 'rising' ? '↑' : g.trend === 'falling' ? '↓' : '→'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

function RiskRing({ score, color }: { score: number; color: string }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" role="img" aria-label={`Risk score ${score} of 100`}>
      <circle cx="36" cy="36" r={r} fill="none" stroke="#1c2536" strokeWidth="7" />
      <circle
        cx="36" cy="36" r={r} fill="none"
        stroke={color} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={`${(score / 100) * c} ${c}`}
        transform="rotate(-90 36 36)"
        style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.16,1,0.3,1)' }}
      />
      <text x="36" y="41" textAnchor="middle" fill="white" fontSize="16" fontWeight="700" fontFamily="monospace">
        {score}
      </text>
    </svg>
  );
}

function Sparkline({ values, marker }: { values: number[]; marker: number }) {
  const w = 260;
  const h = 56;
  const max = Math.max(1, ...values);
  const barW = w / values.length;
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Hourly rainfall forecast chart" preserveAspectRatio="none">
      {values.map((v, i) => (
        <rect
          key={i}
          x={i * barW}
          y={h - (v / max) * (h - 4)}
          width={Math.max(0.5, barW - 0.8)}
          height={(v / max) * (h - 4)}
          fill={i === marker ? '#f8fafc' : '#38bdf8'}
          opacity={i === marker ? 1 : 0.35 + 0.65 * (v / max)}
        />
      ))}
      <line x1={marker * barW} x2={marker * barW} y1={0} y2={h} stroke="#f8fafc" strokeWidth="0.75" strokeDasharray="2 2" />
    </svg>
  );
}
