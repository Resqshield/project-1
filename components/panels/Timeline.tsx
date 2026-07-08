'use client';

import { useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';

/**
 * 72-hour forecast scrubber. Play animates 3 h steps; the rainfall layer
 * re-renders per scrub position. Fully keyboard-accessible (native range input
 * plus Home/End = Now / +72 h).
 */
export default function Timeline() {
  const hour = useAppStore((s) => s.timelineHour);
  const setHour = useAppStore((s) => s.setTimelineHour);
  const playing = useAppStore((s) => s.timelinePlaying);
  const setPlaying = useAppStore((s) => s.setTimelinePlaying);

  // I2 — one-shot attention pulse on the play button shortly after first load,
  // so users notice the forecast is scrubbable. Never loops; reduced-motion safe.
  const [hint, setHint] = useState(false);
  const hinted = useRef(false);
  useEffect(() => {
    if (hinted.current) return;
    hinted.current = true;
    if (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const id = setTimeout(() => setHint(true), 1600);
    return () => clearTimeout(id);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const cur = useAppStore.getState().timelineHour;
      setHour(cur >= 71 ? 0 : cur + 3);
    }, 600);
    return () => clearInterval(id);
  }, [playing, setHour]);

  // X2 — date-aware label. On day boundaries the weekday makes the jump legible.
  const target = new Date(Date.now() + hour * 3600_000);
  const clock = target.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
  const weekday = target.toLocaleDateString('en-IN', { weekday: 'short' });
  const label = hour === 0 ? 'Now' : `+${hour} h · ${weekday} ${clock}`;

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Home') {
      e.preventDefault();
      setHour(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setHour(71);
    }
  };

  return (
    <div className="pointer-events-auto flex items-center gap-3 rounded-xl border border-white/10 bg-ink-900/85 px-4 py-2.5 shadow-2xl backdrop-blur-xl">
      <button
        onClick={() => {
          setPlaying(!playing);
          setHint(false);
        }}
        aria-label={playing ? 'Pause forecast playback' : 'Play 72-hour forecast'}
        aria-keyshortcuts="Space"
        title="Play 72 h forecast"
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent transition hover:bg-accent/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
          hint && !playing ? 'veg-attention' : ''
        }`}
      >
        {playing ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M6 4h4v16H6zM14 4h4v16h-4z" /></svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M8 5v14l11-7z" /></svg>
        )}
      </button>

      <div className="flex-1">
        <div className="mb-1 flex justify-between font-mono text-[10px] text-ink-300">
          <span>Rainfall forecast</span>
          <span className="text-accent tabular-nums">{label}</span>
        </div>
        <input
          type="range"
          min={0}
          max={71}
          step={1}
          value={hour}
          onChange={(e) => setHour(Number(e.target.value))}
          onKeyDown={onKey}
          aria-label="Forecast hour"
          aria-valuetext={label}
          aria-keyshortcuts="Home End ArrowLeft ArrowRight"
          className="veg-range w-full"
        />
        <div className="mt-0.5 flex justify-between font-mono text-[9px] text-ink-400/80" aria-hidden>
          <span>Now</span>
          <span>+24h</span>
          <span>+48h</span>
          <span>+72h</span>
        </div>
      </div>
    </div>
  );
}
