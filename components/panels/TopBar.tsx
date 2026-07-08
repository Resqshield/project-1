'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { DISTRICTS } from '@/lib/districts';
import { searchPlaces, type SearchHit } from '@/lib/search';
import { useAppStore } from '@/store/useAppStore';

export default function TopBar() {
  const selectDistrict = useAppStore((s) => s.selectDistrict);
  const setLayerPanelOpen = useAppStore((s) => s.setLayerPanelOpen);
  const layerPanelOpen = useAppStore((s) => s.layerPanelOpen);
  const basemapMode = useAppStore((s) => s.basemapMode);
  const setBasemapMode = useAppStore((s) => s.setBasemapMode);
  const setInfoOpen = useAppStore((s) => s.setInfoOpen);

  return (
    <header className="pointer-events-auto flex items-center gap-3 rounded-2xl border border-white/10 bg-ink-900/85 px-4 py-2.5 shadow-2xl backdrop-blur-xl">
      <button
        onClick={() => setLayerPanelOpen(!layerPanelOpen)}
        aria-label={layerPanelOpen ? 'Hide layer panel' : 'Show layer panel'}
        aria-expanded={layerPanelOpen}
        className="rounded-lg p-1.5 text-ink-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
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

      <DistrictSearch onPick={(id) => selectDistrict(id)} />

      <LocateButton onLocate={(id) => selectDistrict(id)} />

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
                : 'bg-ink-800/60 text-ink-300 hover:text-ink-200'
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
        className="shrink-0 rounded-lg p-1.5 text-ink-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
        </svg>
      </button>
    </header>
  );
}

/**
 * X1 — free-text place search. Typing a town ("Kochi", "Munnar"), a district,
 * a river station or a pincode resolves to the right district drill-down.
 * ARIA combobox with a listbox; fully keyboard-navigable.
 */
function DistrictSearch({ onPick }: { onPick: (districtId: string) => void }) {
  const [query, setQuery] = useState('');
  const [openList, setOpenList] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const hits = useMemo<SearchHit[]>(() => (query.trim() ? searchPlaces(query) : []), [query]);

  useEffect(() => setActive(0), [query]);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpenList(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const choose = (hit: SearchHit) => {
    onPick(hit.districtId);
    setQuery(hit.label);
    setOpenList(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!openList && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpenList(true);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(hits.length - 1, a + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === 'Enter') {
      if (hits[active]) choose(hits[active]);
    } else if (e.key === 'Escape') {
      setOpenList(false);
    }
  };

  return (
    <div ref={rootRef} className="relative min-w-0 flex-1 md:w-56 md:flex-none">
      <label className="sr-only" htmlFor="district-search">Search town, district or river</label>
      <div className="relative">
        <svg
          className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-300"
          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden
        >
          <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" strokeLinecap="round" />
        </svg>
        <input
          id="district-search"
          type="text"
          role="combobox"
          aria-expanded={openList && hits.length > 0}
          aria-controls="district-search-list"
          aria-autocomplete="list"
          aria-activedescendant={openList && hits[active] ? `hit-${active}` : undefined}
          autoComplete="off"
          placeholder="Search Kochi, Wayanad, 682001…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpenList(true);
          }}
          onFocus={() => query.trim() && setOpenList(true)}
          onKeyDown={onKeyDown}
          className="w-full appearance-none rounded-lg border border-white/10 bg-ink-800/80 py-1.5 pl-8 pr-8 text-sm text-ink-200 placeholder:text-ink-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        />
        {query && (
          <button
            onClick={() => {
              setQuery('');
              useAppStore.getState().selectDistrict(null);
              setOpenList(false);
            }}
            aria-label="Clear search"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-ink-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        )}
      </div>

      {openList && hits.length > 0 && (
        <ul
          id="district-search-list"
          role="listbox"
          className="absolute left-0 right-0 top-full z-30 mt-1 max-h-72 overflow-y-auto rounded-lg border border-white/10 bg-ink-900/95 p-1 shadow-2xl backdrop-blur-xl"
        >
          {hits.map((hit, i) => (
            <li
              key={`${hit.kind}-${hit.label}-${i}`}
              id={`hit-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(hit);
              }}
              className={`flex cursor-pointer items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-sm ${
                i === active ? 'bg-accent/15 text-white' : 'text-ink-200'
              }`}
            >
              <span className="truncate">{hit.label}</span>
              <span className="shrink-0 font-mono text-[10px] text-ink-300">{hit.sub}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** X4 — geolocate and jump to the user's district. */
function LocateButton({ onLocate }: { onLocate: (districtId: string) => void }) {
  const [state, setState] = useState<'idle' | 'locating' | 'error'>('idle');

  const locate = () => {
    if (!('geolocation' in navigator)) {
      setState('error');
      return;
    }
    setState('locating');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { longitude, latitude } = pos.coords;
        const nearest = DISTRICTS.reduce(
          (best, d) => {
            const dx = d.centroid[0] - longitude;
            const dy = d.centroid[1] - latitude;
            const dist = dx * dx + dy * dy;
            return dist < best.dist ? { id: d.id, dist } : best;
          },
          { id: DISTRICTS[0].id, dist: Infinity }
        );
        onLocate(nearest.id);
        setState('idle');
      },
      () => setState('error'),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 }
    );
  };

  return (
    <button
      onClick={locate}
      aria-label="Find my district"
      title={state === 'error' ? 'Location unavailable' : 'Find my district'}
      className={`shrink-0 rounded-lg p-1.5 transition hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
        state === 'error' ? 'text-sev-red' : 'text-ink-300 hover:text-white'
      }`}
    >
      {state === 'locating' ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden className="animate-spin">
          <path d="M21 12a9 9 0 1 1-6.2-8.6" strokeLinecap="round" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" strokeLinecap="round" />
        </svg>
      )}
    </button>
  );
}
