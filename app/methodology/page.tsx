import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Methodology — Vegvisir',
  description: 'How the Vegvisir composite risk index is computed, and where every data layer comes from.',
};

export default function MethodologyPage() {
  return (
    <div className="min-h-screen bg-ink-950 px-6 py-12">
      <article className="mx-auto max-w-2xl">
        <Link href="/" className="font-mono text-xs text-accent hover:underline">
          ← back to the map
        </Link>

        <h1 className="mt-6 font-display text-3xl font-bold text-white">Methodology & data sources</h1>
        <p className="mt-3 leading-relaxed text-ink-400">
          Vegvisir is a visualization and decision-support layer. Official warnings always come from
          IMD, NDMA and the state disaster management authorities — treat their advisories as
          authoritative.
        </p>

        <h2 className="mt-10 font-display text-xl font-semibold text-white">Composite risk index (v1)</h2>
        <p className="mt-3 leading-relaxed text-ink-200">
          Each district's score (0–100) is a transparent weighted overlay, recomputed every 15
          minutes from live rainfall:
        </p>
        <pre className="mt-4 overflow-x-auto rounded-xl border border-white/10 bg-ink-900 p-4 font-mono text-xs leading-relaxed text-accent">
{`risk = 0.40 · rain        (observed 24 h + forecast 48 h, ÷250 mm)
     + 0.25 · landslide   (NRSC atlas susceptibility × rain amplification)
     + 0.25 · flood       (historical proneness × rain amplification)
     + 0.10 · exposure    (population density ÷ 1600 /km²)

amplification = 0.25 + 0.75 · rain-normalized`}
        </pre>
        <p className="mt-3 text-sm leading-relaxed text-ink-400">
          Terrain factors are rain-amplified because a susceptible slope is chiefly dangerous while it
          is raining. Severity bands: 0–24 Normal, 25–44 Watch, 45–64 Alert, 65+ Severe. Weights are
          published so the model can be audited and challenged; calibration against the 2018/2019
          Kerala flood record is on the roadmap before any operational use.
        </p>

        <h2 className="mt-10 font-display text-xl font-semibold text-white">Data tiers</h2>
        <ul className="mt-3 space-y-3 text-sm leading-relaxed text-ink-200">
          <li>
            <strong className="text-emerald-400">LIVE</strong> — streamed from public feeds through
            cached API routes: rainfall (Open-Meteo multi-model), river discharge (GloFAS/Copernicus
            via the Open-Meteo Flood API, sampled at CWC station sites), hazard events (GDACS),
            earthquakes (USGS), satellite imagery (NASA GIBS / VIIRS).
          </li>
          <li>
            <strong className="text-amber-400">SAMPLE</strong> — real facility locations with a
            curated, illustrative list: hospitals & shelters (pending OSM/KSDMA extraction).
          </li>
        </ul>

        <h2 className="mt-10 font-display text-xl font-semibold text-white">River status thresholds</h2>
        <p className="mt-3 text-sm leading-relaxed text-ink-400">
          Each station is coloured by today's modelled discharge relative to its own trailing
          31-day median: <span className="text-emerald-400">normal</span> below 1.5×,{' '}
          <span className="text-orange-400">elevated</span> from 1.5×, and{' '}
          <span className="text-red-400">high</span> from 3×. This anomaly approach is
          self-calibrating per river but is not a substitute for CWC's official warning/danger
          levels, which are the planned replacement.
        </p>

        <h2 className="mt-10 font-display text-xl font-semibold text-white">Static factors</h2>
        <p className="mt-3 text-sm leading-relaxed text-ink-400">
          Landslide susceptibility per district is derived from the NRSC/ISRO Landslide Atlas of
          India hotspot rankings (the Western Ghats account for ~14.7% of national exposure). Flood
          proneness reflects the 2018/2019 flood footprints and each district's share of low-lying
          terrain. Population density is Census-derived (people/km²).
        </p>

        <h2 className="mt-10 font-display text-xl font-semibold text-white">Production integration targets</h2>
        <p className="mt-3 text-sm leading-relaxed text-ink-400">
          NDMA SACHET CAP alert feed · IMD official API (api.imd.gov.in) · CWC flood-forecast river
          levels · INCOIS ocean-state & high-wave alerts · NRSC Bhuvan WMS hazard zonation layers ·
          WorldPop gridded population. The ingestion architecture treats every upstream source as
          unreliable: adapters validate, normalize and cache, and the UI surfaces per-layer freshness.
        </p>

        <footer className="mt-12 border-t border-white/10 pt-6 font-mono text-[11px] text-ink-400">
          Vegvisir · open data, open methodology · built for Kerala & South India · made by{' '}
          <span className="text-accent/80">AJ</span>
        </footer>
      </article>
    </div>
  );
}
