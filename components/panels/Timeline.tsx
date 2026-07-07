'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';

/**
 * 72-hour forecast scrubber. Play animates 3 h steps; the rainfall layer
 * re-renders per scrub position. Fully keyboard-accessible (native range input).
 */
export default function Timeline() {
  const hour = useAppStore((s) => s.timelineHour);
  const setHour = useAppStore((s) => s.setTimelineHour);
  const playing = useAppStore((s) => s.timelinePlaying);
  const setPlaying = useAppStore((s) => s.setTimelinePlaying);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const cur = useAppStore.getState().timelineHour;
      setHour(cur >= 71 ? 0 : cur + 3);
    }, 600);
    return () => clearInterval(id);
  }, [playing, setHour]);

  const label =
    hour === 0
      ? 'Now'
      : `+${hour} h (${new Date(Date.now() + hour * 3600_000).toLocaleString('en-IN', {
          weekday: 'short',
          hour: 'numeric',
        })})`;

  return (
    <div className="pointer-events-auto flex items-center gap-3 rounded-xl border border-white/10 bg-ink-900/80 px-4 py-2.5 shadow-2xl backdrop-blur-xl">
      <button
        onClick={() => setPlaying(!playing)}
        aria-label={playing ? 'Pause forecast playback' : 'Play 72-hour forecast'}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent transition hover:bg-accent/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {playing ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M6 4h4v16H6zM14 4h4v16h-4z" /></svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M8 5v14l11-7z" /></svg>
        )}
      </button>

      <div className="flex-1">
        <div className="mb-1 flex justify-between font-mono text-[10px] text-ink-400">
          <span>Rainfall forecast</span>
          <span className="text-accent">{label}</span>
        </div>
        <input
          type="range"
          min={0}
          max={71}
          step={1}
          value={hour}
          onChange={(e) => setHour(Number(e.target.value))}
          aria-label="Forecast hour"
          aria-valuetext={label}
          className="veg-range w-full"
        />
      </div>
    </div>
  );
}
