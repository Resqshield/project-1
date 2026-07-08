'use client';

import { useEffect, useRef, useState } from 'react';
import { DISTRICT_BY_ID } from '@/lib/districts';
import { SEVERITY_LABELS, mm, qty } from '@/lib/format';
import { SEVERITY_COLORS } from '@/lib/types';
import type { RainPoint, RiskScore, RiverStatus } from '@/lib/types';
import { useAppStore } from '@/store/useAppStore';

interface Props {
  risk: RiskScore[] | null;
  rain: RainPoint[] | null;
  rivers: RiverStatus[] | null;
  /** 'primary' follows selectedDistrictId; 'compare' follows compareDistrictId (X5). */
  mode?: 'primary' | 'compare';
}

const RIVER_STATUS_COLOR: Record<RiverStatus['status'], string> = {
  normal: '#22c55e',
  elevated: '#f97316',
  high: '#ef4444',
};

/** District drill-down: risk ring, driver bars, 72 h rain sparkline, rivers. */
export default function DetailPanel({ risk, rain, rivers, mode = 'primary' }: Props) {
  const selectedId = useAppStore((s) => s.selectedDistrictId);
  const compareId = useAppStore((s) => s.compareDistrictId);
  const selectDistrict = useAppStore((s) => s.selectDistrict);
  const setCompareDistrict = useAppStore((s) => s.setCompareDistrict);
  const timelineHour = useAppStore((s) => s.timelineHour);
  const highlightedStationId = useAppStore((s) => s.highlightedStationId);
  const highlightStation = useAppStore((s) => s.highlightStation);

  const id = mode === 'compare' ? compareId : selectedId;

  const close = () => {
    if (mode === 'compare') setCompareDistrict(null);
    else selectDistrict(null); // primary close also clears the compare pin
  };

  // L2 — Escape closes the panel (power users expect it, not just the ✕).
  useEffect(() => {
    if (!id) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, mode]);

  // R1 — swipe-down-to-dismiss on the mobile bottom sheet.
  const sheetRef = useRef<HTMLElement>(null);
  const [dragY, setDragY] = useState(0);
  const dragStart = useRef<number | null>(null);
  const onHandleDown = (e: React.PointerEvent) => {
    dragStart.current = e.clientY;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };
  const onHandleMove = (e: React.PointerEvent) => {
    if (dragStart.current == null) return;
    setDragY(Math.max(0, e.clientY - dragStart.current));
  };
  const onHandleUp = () => {
    if (dragStart.current == null) return;
    if (dragY > 80) close();
    dragStart.current = null;
    setDragY(0);
  };

  if (!id) return null;
  const district = DISTRICT_BY_ID.get(id);
  if (!district) return null;

  const loading = risk === null; // feeds not resolved yet (L6)
  const r = risk?.find((x) => x.districtId === id);
  const rf = rain?.find((x) => x.districtId === id);
  const districtRivers = (rivers ?? []).filter((g) => g.districtId === id);
  const color = r ? SEVERITY_COLORS[r.severity] : '#64748b';

  return (
    <aside
      ref={sheetRef}
      aria-label={`${district.name} district details${mode === 'compare' ? ' (comparison)' : ''}`}
      style={dragY ? { transform: `translateY(${dragY}px)`, transition: 'none' } : undefined}
      className="pointer-events-auto w-full animate-slide-up overflow-y-auto rounded-2xl border border-white/10 bg-ink-900/85 shadow-2xl backdrop-blur-xl max-h-[58dvh] md:w-80 md:max-h-[calc(100dvh-2rem)]"
    >
      {/* R1 — mobile drag handle (hidden on desktop) */}
      <div
        className="flex touch-none justify-center pt-2 md:hidden"
        onPointerDown={onHandleDown}
        onPointerMove={onHandleMove}
        onPointerUp={onHandleUp}
        onPointerCancel={onHandleUp}
        role="button"
        tabIndex={-1}
        aria-label="Drag down to dismiss"
      >
        <span className="h-1 w-10 rounded-full bg-white/25" aria-hidden />
      </div>

      <div className="p-4 pt-3">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-lg font-bold text-white">{district.name}</h2>
              {mode === 'compare' && (
                <span className="rounded-full bg-accent/15 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-accent">
                  compare
                </span>
              )}
            </div>
            {/* T3 — softened metric: lowercase, subtle divider */}
            <p className="text-[11px] text-ink-300">
              <span className="font-mono tabular-nums">{district.popDensity.toLocaleString('en-IN')}</span>{' '}
              people/km²{district.coastal ? ' · coastal' : ''}
            </p>
          </div>
          <button
            onClick={close}
            aria-label={mode === 'compare' ? 'Close comparison' : 'Close district details'}
            className="rounded-lg p-1.5 text-ink-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>

        {loading ? (
          <SkeletonBody />
        ) : (
          <>
            {/* Risk ring */}
            <div className="mb-4 flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.03] p-3">
              <RiskRing score={r?.score ?? 0} color={color} />
              <div>
                <p className="text-2xl font-bold" style={{ color }}>
                  {r ? SEVERITY_LABELS[r.severity] : '—'}
                </p>
                <p className="text-xs text-ink-300">Composite risk index</p>
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
                    <div className="mb-0.5 flex justify-between text-[10px] text-ink-300">
                      <span>{label}</span>
                      <span className="font-mono tabular-nums">{Math.round(v * 100)}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-ink-700" role="img" aria-label={`${label}: ${Math.round(v * 100)} of 100`}>
                      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${v * 100}%`, backgroundColor: c }} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Rain — T4: two-stat row with small labels above values */}
            {rf && (
              <div className="mb-4 rounded-xl border border-white/5 bg-white/[0.03] p-3">
                <div className="mb-2 flex items-baseline justify-between gap-3">
                  <h3 className="text-xs font-semibold text-ink-200">Rainfall — next 72 h</h3>
                  <div className="flex gap-4 text-right">
                    <Stat label="24 h" value={mm(rf.next24h)} />
                    <Stat label="72 h" value={mm(rf.next72h)} />
                  </div>
                </div>
                <Sparkline values={rf.hourly} marker={timelineHour} />
                <p className="mt-1.5 font-mono text-[10px] text-ink-300 tabular-nums">past 24 h: {mm(rf.past24h)} · Open-Meteo</p>
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
                    <RiverRow
                      key={g.id}
                      station={g}
                      flash={mode === 'primary' && highlightedStationId === g.id}
                      onFlashEnd={() => highlightStation(null)}
                    />
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[9px] uppercase tracking-wider text-ink-400">{label}</p>
      <p className="font-mono text-xs tabular-nums text-ink-200">{value}</p>
    </div>
  );
}

function RiverRow({
  station: g,
  flash,
  onFlashEnd,
}: {
  station: RiverStatus;
  flash: boolean;
  onFlashEnd: () => void;
}) {
  return (
    <li
      className={`-mx-1 flex items-center justify-between gap-2 rounded-md px-1 py-0.5 text-xs ${flash ? 'veg-row-flash' : ''}`}
      onAnimationEnd={() => flash && onFlashEnd()}
    >
      <span className="min-w-0 truncate text-ink-200">
        {g.name} <span className="text-ink-300">· {g.river}</span>
      </span>
      <span
        className="shrink-0 font-mono tabular-nums"
        style={{ color: RIVER_STATUS_COLOR[g.status] }}
        title={`${g.ratio}× the 31-day median flow`}
      >
        {qty(g.dischargeM3s, 'm³/s')} {g.trend === 'rising' ? '↑' : g.trend === 'falling' ? '↓' : '→'}
      </span>
    </li>
  );
}

/** L6 — shimmering skeleton while the feeds resolve. */
function SkeletonBody() {
  return (
    <div aria-hidden>
      <div className="mb-4 flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.03] p-3">
        <div className="veg-skeleton h-[72px] w-[72px] rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="veg-skeleton h-5 w-24" />
          <div className="veg-skeleton h-3 w-32" />
        </div>
      </div>
      <div className="mb-4 space-y-2.5">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="space-y-1">
            <div className="veg-skeleton h-2.5 w-28" />
            <div className="veg-skeleton h-1.5 w-full" />
          </div>
        ))}
      </div>
      <div className="veg-skeleton h-20 w-full rounded-xl" />
    </div>
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
      <text x="36" y="41" textAnchor="middle" fill="white" fontSize="16" fontWeight="700" fontFamily="monospace" style={{ fontVariantNumeric: 'tabular-nums' }}>
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
