'use client';

import type { HazardAlert } from '@/lib/types';
import { SEVERITY_COLORS } from '@/lib/types';
import { timeAgo } from '@/lib/format';

interface Props {
  alerts: HazardAlert[] | null;
  /** feed timestamp — powers the "last checked" line of the all-clear state */
  updatedAt?: string | null;
  error?: boolean;
}

export default function AlertTicker({ alerts, updatedAt, error }: Props) {
  const items = (alerts ?? []).filter((a) => a.severity !== 'green').slice(0, 12);

  // L1 — never render a silently-empty edge. When there are no active alerts we
  // show an explicit "all clear" chip so users can tell "no alerts" from
  // "alerts broken", with the last-checked time for confidence.
  if (!items.length) {
    // While the very first fetch is still in flight, show nothing (the freshness
    // badge already communicates "loading").
    if (!alerts && !error) return null;
    return (
      <div
        className="pointer-events-auto inline-flex items-center gap-2 rounded-xl border border-white/10 bg-ink-900/85 px-3 py-2 shadow-2xl backdrop-blur-xl"
        role="status"
        aria-live="polite"
      >
        {error ? (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-sev-red" aria-hidden />
            <span className="text-xs text-ink-200">Alert feed unavailable</span>
            <span className="font-mono text-[10px] text-ink-300">— retrying</span>
          </>
        ) : (
          <>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5" aria-hidden>
              <path d="M20 6 9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="text-xs text-ink-200">No active hazard alerts in the region</span>
            {updatedAt && (
              <span className="font-mono text-[10px] text-ink-300">· checked {timeAgo(updatedAt)}</span>
            )}
          </>
        )}
      </div>
    );
  }

  // Duplicate the list so the CSS marquee loops seamlessly.
  const loop = [...items, ...items];

  return (
    <div
      className="pointer-events-auto overflow-hidden rounded-xl border border-white/10 bg-ink-900/85 shadow-2xl backdrop-blur-xl"
      role="region"
      aria-label="Active hazard alerts"
    >
      <div className="flex items-center">
        <span className="z-10 flex shrink-0 items-center gap-1.5 border-r border-white/10 bg-ink-900/95 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-sev-red">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sev-red" aria-hidden />
          Alerts
        </span>
        <div className="relative flex-1 overflow-hidden py-2 [mask-image:linear-gradient(to_right,transparent,black_24px,black_calc(100%-24px),transparent)]">
          <div className="flex w-max animate-ticker gap-8 motion-reduce:animate-none motion-reduce:flex-wrap">
            {loop.map((a, i) => (
              <span key={`${a.id}-${i}`} className="flex items-center gap-2 whitespace-nowrap text-xs text-ink-200" aria-hidden={i >= items.length}>
                <span style={{ color: SEVERITY_COLORS[a.severity] }} aria-hidden>●</span>
                <span className="font-medium">{a.title}</span>
                <span className="text-ink-300">· {a.source} · {timeAgo(a.issuedAt)}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
