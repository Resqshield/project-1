'use client';

import { DISTRICTS } from '@/lib/districts';
import { useAppStore } from '@/store/useAppStore';

export default function TopBar() {
  const selectDistrict = useAppStore((s) => s.selectDistrict);
  const selectedDistrictId = useAppStore((s) => s.selectedDistrictId);
  const setLayerPanelOpen = useAppStore((s) => s.setLayerPanelOpen);
  const layerPanelOpen = useAppStore((s) => s.layerPanelOpen);
  const basemapMode = useAppStore((s) => s.basemapMode);
  const setBasemapMode = useAppStore((s) => s.setBasemapMode);
  const setInfoOpen = useAppStore((s) => s.setInfoOpen);

  return (
    <header className="pointer-events-auto flex items-center gap-3 rounded-2xl border border-white/10 bg-ink-900/70 px-4 py-2.5 shadow-2xl backdrop-blur-xl">
      <button
        onClick={() => setLayerPanelOpen(!layerPanelOpen)}
        aria-label={layerPanelOpen ? 'Hide layer panel' : 'Show layer panel'}
        aria-expanded={layerPanelOpen}
        className="rounded-lg p-1.5 text-ink-400 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinejoin="round" />
        </svg>
      </button>

      <div className="flex items-baseline gap-2">
        <span className="font-display text-lg font-bold tracking-tight text-white">VEGVISIR</span>
        <span className="hidden font-mono text-[10px] uppercase tracking-[0.3em] text-accent/70 sm:inline">
          disaster intelligence
        </span>
      </div>

      <div className="mx-2 hidden h-5 w-px bg-white/10 md:block" />

      <label className="relative flex-1 md:max-w-xs">
        <span className="sr-only">Jump to district</span>
        <select
          value={selectedDistrictId ?? ''}
          onChange={(e) => selectDistrict(e.target.value || null)}
          className="w-full appearance-none rounded-lg border border-white/10 bg-ink-800/80 px-3 py-1.5 pr-8 text-sm text-ink-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <option value="">All of Kerala…</option>
          {DISTRICTS.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <svg
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-400"
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </label>

      {/* Basemap mode — dark data view vs photoreal satellite */}
      <div
        role="group"
        aria-label="Basemap style"
        className="hidden shrink-0 overflow-hidden rounded-lg border border-white/10 sm:flex"
      >
        {(['dark', 'satellite'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setBasemapMode(mode)}
            aria-pressed={basemapMode === mode}
            className={`px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              basemapMode === mode
                ? 'bg-accent/20 text-accent'
                : 'bg-ink-800/60 text-ink-400 hover:text-ink-200'
            }`}
          >
            {mode === 'dark' ? 'Dark' : 'Satellite'}
          </button>
        ))}
      </div>

      {/* Data sources & disclaimer */}
      <button
        onClick={() => setInfoOpen(true)}
        aria-label="Data sources and disclaimer"
        title="Data sources & disclaimer"
        className="shrink-0 rounded-lg p-1.5 text-ink-400 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
        </svg>
      </button>
    </header>
  );
}
