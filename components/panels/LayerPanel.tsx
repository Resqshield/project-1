'use client';

import { LAYERS } from '@/lib/layers';
import type { LegendItem } from '@/lib/types';
import { useAppStore } from '@/store/useAppStore';
import { TierBadge } from '@/components/ui/Badge';
import LayerIcon from '@/components/ui/LayerIcon';

export function LegendSwatch({ color, shape }: Pick<LegendItem, 'color' | 'shape'>) {
  if (shape === 'fill') {
    // C2 — render fill chips the way the map paints them: the colour composited
    // at low opacity over the dark surface, so the chip matches the choropleth
    // instead of showing a saturated block.
    return (
      <span aria-hidden className="h-2.5 w-3.5 shrink-0 overflow-hidden rounded-sm bg-ink-950">
        <span className="block h-full w-full" style={{ backgroundColor: color, opacity: 0.4 }} />
      </span>
    );
  }
  if (shape === 'size') {
    return (
      <span aria-hidden className="flex shrink-0 items-end gap-0.5">
        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color, opacity: 0.5 }} />
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color, opacity: 0.8 }} />
      </span>
    );
  }
  return <span aria-hidden className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />;
}

const GROUPS = ['Hazards', 'Water', 'People & Infrastructure', 'Imagery'] as const;

export default function LayerPanel() {
  const activeLayers = useAppStore((s) => s.activeLayers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const open = useAppStore((s) => s.layerPanelOpen);
  const collapsed = useAppStore((s) => s.layerCollapsed);
  const setCollapsed = useAppStore((s) => s.setLayerCollapsed);

  if (!open) return null;

  // L4 — collapsed icon rail. Reclaims ~280px of map; the distinctive animated
  // icons carry meaning on their own. Click an icon to toggle it, or expand.
  if (collapsed) {
    return (
      <aside
        aria-label="Map layers (collapsed)"
        className="pointer-events-auto flex w-12 animate-slide-up flex-col items-center gap-1 rounded-2xl border border-white/10 bg-ink-900/85 p-1.5 shadow-2xl backdrop-blur-xl"
      >
        <button
          onClick={() => setCollapsed(false)}
          aria-label="Expand layer panel"
          aria-expanded={false}
          className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="m9 18 6-6-6-6" /></svg>
        </button>
        <span className="my-0.5 h-px w-6 bg-white/10" aria-hidden />
        {LAYERS.map((layer) => {
          const on = activeLayers.has(layer.id);
          return (
            <button
              key={layer.id}
              onClick={() => toggleLayer(layer.id)}
              role="switch"
              aria-checked={on}
              title={`${layer.label} — ${on ? 'on' : 'off'}`}
              className={`flex h-9 w-9 items-center justify-center rounded-xl border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                on ? 'border-accent/30 bg-accent/10' : 'border-transparent hover:bg-white/[0.07]'
              }`}
            >
              <LayerIcon id={layer.id} active={on} />
            </button>
          );
        })}
      </aside>
    );
  }

  return (
    <aside
      aria-label="Map layers"
      className="pointer-events-auto w-72 max-w-[calc(100vw-1.5rem)] animate-slide-up overflow-y-auto rounded-2xl border border-white/10 bg-ink-900/85 p-4 shadow-2xl backdrop-blur-xl max-h-[calc(100dvh-21rem)] md:max-h-[calc(100dvh-16rem)]"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-mono text-[10px] uppercase tracking-[0.25em] text-ink-300">Data layers</h2>
        <button
          onClick={() => setCollapsed(true)}
          aria-label="Collapse layer panel to icon rail"
          title="Collapse to icon rail"
          className="rounded-lg p-1 text-ink-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="m15 18-6-6 6-6" /></svg>
        </button>
      </div>

      {/* C1 — disambiguate the choropleth: without this, near-black districts
          read the same as "out of scope". */}
      <p className="mb-3 flex items-center gap-1.5 rounded-lg bg-white/[0.03] px-2.5 py-1.5 text-[10px] text-ink-300">
        <span aria-hidden className="h-2.5 w-3.5 shrink-0 overflow-hidden rounded-sm bg-ink-950">
          <span className="block h-full w-full bg-accent" style={{ opacity: 0.4 }} />
        </span>
        Coloured districts = monitored region (Kerala)
      </p>

      {GROUPS.map((group) => {
        const layers = LAYERS.filter((l) => l.group === group);
        if (!layers.length) return null;
        return (
          <section key={group} className="mb-4 last:mb-0">
            {/* L3 — sticky group header keeps context while scrolling */}
            <h3 className="sticky top-0 z-10 -mx-1 mb-2 bg-ink-900/90 px-1 py-1 text-xs font-semibold text-ink-200 backdrop-blur">
              {group}
            </h3>
            <ul className="space-y-1.5">
              {layers.map((layer) => {
                const on = activeLayers.has(layer.id);
                return (
                  <li key={layer.id}>
                    <button
                      onClick={() => toggleLayer(layer.id)}
                      role="switch"
                      aria-checked={on}
                      title={layer.description}
                      className={`group flex w-full items-center gap-2.5 rounded-xl border px-3 py-2 text-left transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                        on
                          ? 'border-accent/30 bg-accent/10 shadow-[0_0_16px_-6px_rgba(56,189,248,0.35)]'
                          : 'border-white/5 bg-white/[0.03] hover:translate-x-0.5 hover:bg-white/[0.07]'
                      }`}
                    >
                      {/* no scale transform — scaling rasterizes the SVG and blurs it */}
                      <span className="shrink-0">
                        <LayerIcon id={layer.id} active={on} />
                      </span>
                      <span className={`flex-1 text-xs transition-colors ${on ? 'text-white' : 'text-ink-200'}`}>
                        {layer.label}
                      </span>
                      <TierBadge tier={layer.tier} />
                      <span
                        aria-hidden
                        className={`relative h-4 w-7 shrink-0 rounded-full transition ${on ? 'bg-accent' : 'bg-ink-700'}`}
                      >
                        <span
                          className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-all ${on ? 'left-3.5' : 'left-0.5'}`}
                        />
                      </span>
                    </button>

                    {/* How to read this layer — shown while active */}
                    {on && layer.legend.length > 0 && (
                      <div
                        className="mt-1 flex animate-fade-in flex-wrap items-center gap-x-3 gap-y-1 px-3 pb-0.5"
                        aria-label={`${layer.label} legend`}
                      >
                        {layer.legend.map((item) => (
                          <span key={item.label} className="flex items-center gap-1.5 text-[10px] text-ink-300">
                            <LegendSwatch color={item.color} shape={item.shape} />
                            {item.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}

      <p className="mt-2 border-t border-white/5 pt-3 text-[10px] leading-relaxed text-ink-300">
        <span className="text-emerald-400">LIVE</span> layers stream from public feeds ·{' '}
        <span className="text-amber-400">SAMPLE</span> layers show real locations with illustrative
        readings pending official adapters. <a href="/methodology" className="text-accent underline-offset-2 hover:underline">Methodology →</a>
      </p>
    </aside>
  );
}
