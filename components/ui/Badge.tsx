import type { DataTier } from '@/lib/types';

export function TierBadge({ tier }: { tier: DataTier }) {
  return tier === 'live' ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" aria-hidden />
      Live
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-amber-400">
      Sample
    </span>
  );
}

export function FreshnessBadge({ updatedAt, error }: { updatedAt: string | null; error: boolean }) {
  if (error) {
    return <span className="font-mono text-[10px] text-sev-red">source unavailable</span>;
  }
  if (!updatedAt) {
    return <span className="font-mono text-[10px] text-ink-400">loading…</span>;
  }
  const mins = Math.round((Date.now() - Date.parse(updatedAt)) / 60000);
  const stale = mins > 60;
  return (
    <span className={`font-mono text-[10px] ${stale ? 'text-amber-400' : 'text-ink-400'}`}>
      updated {mins < 1 ? 'just now' : `${mins} min ago`}
    </span>
  );
}
