'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';

const SHORTCUTS: [string, string][] = [
  ['?', 'Show / hide this help'],
  ['Esc', 'Close panel, popup or dialog'],
  ['Space', 'Play / pause the 72 h forecast'],
  ['← / →', 'Scrub the forecast timeline'],
  ['Home / End', 'Jump to Now / +72 h'],
  ['Double-click', 'Pin a district to compare side-by-side'],
];

/**
 * A5 — keyboard-shortcuts help. Opens on "?", closes on "?" again or Esc.
 * Also owns the global "?" hotkey so shortcuts are discoverable.
 */
export default function ShortcutsOverlay() {
  const open = useAppStore((s) => s.shortcutsOpen);
  const setOpen = useAppStore((s) => s.setShortcutsOpen);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const typing = el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
      if (e.key === '?' && !typing) {
        e.preventDefault();
        setOpen(!useAppStore.getState().shortcutsOpen);
      } else if (e.key === 'Escape' && useAppStore.getState().shortcutsOpen) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setOpen]);

  if (!open) return null;

  return (
    <div
      className="pointer-events-auto fixed inset-0 z-[70] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
    >
      <button className="absolute inset-0 bg-black/60 backdrop-blur-sm" aria-label="Close keyboard shortcuts" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-sm animate-slide-up rounded-2xl border border-white/10 bg-ink-900/95 p-6 shadow-2xl backdrop-blur-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 id="shortcuts-title" className="font-display text-lg font-bold text-white">Keyboard shortcuts</h2>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close"
            className="rounded-lg p-1.5 text-ink-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <dl className="space-y-2.5">
          {SHORTCUTS.map(([key, desc]) => (
            <div key={key} className="flex items-center justify-between gap-4">
              <dt className="shrink-0">
                <kbd className="rounded-md border border-white/15 bg-white/[0.06] px-2 py-1 font-mono text-[11px] text-ink-200">{key}</kbd>
              </dt>
              <dd className="text-right text-xs text-ink-300">{desc}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
