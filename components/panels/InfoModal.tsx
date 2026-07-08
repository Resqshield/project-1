'use client';

import { useEffect, useRef } from 'react';
import { useAppStore } from '@/store/useAppStore';

interface SourceRow {
  name: string;
  provides: string;
  tier: 'LIVE' | 'SAMPLE' | 'STATIC';
  url: string;
}

const SOURCES: SourceRow[] = [
  { name: 'Open-Meteo', provides: 'Rainfall — observed + 72 h multi-model forecast (CC-BY 4.0)', tier: 'LIVE', url: 'https://open-meteo.com' },
  { name: 'GDACS (EC JRC / UN OCHA)', provides: 'Multi-hazard disaster alerts — floods, cyclones, earthquakes', tier: 'LIVE', url: 'https://www.gdacs.org' },
  { name: 'USGS', provides: 'Earthquakes, past 7 days, peninsular India region', tier: 'LIVE', url: 'https://earthquake.usgs.gov' },
  { name: 'NASA GIBS', provides: 'VIIRS true-colour satellite imagery, updated daily', tier: 'LIVE', url: 'https://www.earthdata.nasa.gov/engage/gibs' },
  { name: 'CARTO / OpenStreetMap', provides: 'Dark basemap — © OpenStreetMap contributors', tier: 'LIVE', url: 'https://carto.com/basemaps' },
  { name: 'Esri World Imagery', provides: 'Satellite basemap — © Esri, Maxar, Earthstar Geographics', tier: 'LIVE', url: 'https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9' },
  { name: 'NRSC / ISRO Landslide Atlas', provides: 'District landslide susceptibility rankings (derived)', tier: 'STATIC', url: 'https://www.nrsc.gov.in' },
  { name: 'Census of India', provides: 'District population density (exposure factor)', tier: 'STATIC', url: 'https://censusindia.gov.in' },
  { name: 'Community GeoJSON (datameet)', provides: 'Kerala district boundaries', tier: 'STATIC', url: 'https://github.com/datameet' },
  { name: 'GloFAS via Open-Meteo Flood API', provides: 'River discharge at CWC station sites — modelled, updated daily (Copernicus)', tier: 'LIVE', url: 'https://open-meteo.com/en/docs/flood-api' },
  { name: 'Curated facility list', provides: 'Hospitals, relief camps, fire stations', tier: 'SAMPLE', url: 'https://sdma.kerala.gov.in' },
];

const TIER_STYLE: Record<SourceRow['tier'], string> = {
  LIVE: 'bg-emerald-500/15 text-emerald-400',
  SAMPLE: 'bg-amber-500/15 text-amber-400',
  STATIC: 'bg-sky-500/15 text-sky-400',
};

/** Accessible modal: data provenance + operational disclaimer. */
export default function InfoModal() {
  const open = useAppStore((s) => s.infoOpen);
  const setOpen = useAppStore((s) => s.setInfoOpen);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, setOpen]);

  if (!open) return null;

  return (
    <div
      className="pointer-events-auto fixed inset-0 z-[60] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="info-title"
    >
      <button
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        aria-label="Close data sources dialog"
        onClick={() => setOpen(false)}
      />
      <div className="relative max-h-[85vh] w-full max-w-lg animate-slide-up overflow-y-auto rounded-2xl border border-white/10 bg-ink-900/95 p-6 shadow-2xl backdrop-blur-xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 id="info-title" className="font-display text-xl font-bold text-white">
              Data sources
            </h2>
            <p className="mt-1 text-xs text-ink-400">Where every layer on this map comes from.</p>
          </div>
          <button
            ref={closeRef}
            onClick={() => setOpen(false)}
            aria-label="Close"
            className="rounded-lg p-2 text-ink-400 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>

        <ul className="space-y-2">
          {SOURCES.map((s) => (
            <li key={s.name} className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2.5">
              <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-mono text-[9px] font-semibold ${TIER_STYLE[s.tier]}`}>
                {s.tier}
              </span>
              <div className="min-w-0">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-ink-200 underline-offset-2 hover:text-accent hover:underline"
                >
                  {s.name} ↗
                </a>
                <p className="text-xs leading-relaxed text-ink-400">{s.provides}</p>
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-5 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
          <h3 className="mb-1 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-400">Disclaimer</h3>
          <p className="text-xs leading-relaxed text-ink-200">
            Vegvisir is a <strong>visualization and decision-support tool</strong>, not a warning
            authority. Official alerts and advisories are issued by the India Meteorological
            Department (IMD), the National Disaster Management Authority (NDMA/SACHET), the Central
            Water Commission (CWC), INCOIS, and state disaster management authorities such as KSDMA —
            always treat their instructions as authoritative. Layers badged <em>SAMPLE</em> show real
            locations with illustrative readings. The composite risk index is an uncalibrated
            experimental model; its formula and weights are published on the{' '}
            <a href="/methodology" className="text-accent underline-offset-2 hover:underline">methodology page</a>.
          </p>
        </div>

        <p className="mt-4 text-center font-mono text-[10px] text-ink-400">
          Vegvisir · open data · open methodology · MIT
        </p>
      </div>
    </div>
  );
}
