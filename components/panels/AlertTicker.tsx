'use client';

import type { HazardAlert } from '@/lib/types';
import { SEVERITY_COLORS } from '@/lib/types';
import { timeAgo } from '@/lib/format';

export default function AlertTicker({ alerts }: { alerts: HazardAlert[] | null }) {
  const items = (alerts ?? []).filter((a) => a.severity !== 'green').slice(0, 12);
  if (!items.length) return null;

  // Duplicate the list so the CSS marquee loops seamlessly.
  const loop = [...items, ...items];

  return (
    <div
      className="pointer-events-auto overflow-hidden rounded-xl border border-white/10 bg-ink-900/80 shadow-2xl backdrop-blur-xl"
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
                <span className="text-ink-400">· {a.source} · {timeAgo(a.issuedAt)}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
