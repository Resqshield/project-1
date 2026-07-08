'use client';

import { LAYERS } from '@/lib/layers';
import type { LegendItem } from '@/lib/types';
import { useAppStore } from '@/store/useAppStore';
import { TierBadge } from '@/components/ui/Badge';
import LayerIcon from '@/components/ui/LayerIcon';

export function LegendSwatch({ color, shape }: Pick<LegendItem, 'color' | 'shape'>) {
  if (shape === 'fill') {
    return <span aria-hidden className="h-2.5 w-3.5 shrink-0 rounded-sm" style={{ backgroundColor: color, opacity: 0.75 }} />;
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

  if (!open) return null;

  return (
    <aside
      aria-label="Map layers"
      className="pointer-events-auto max-h-[60vh] w-72 animate-slide-up overflow-y-auto rounded-2xl border border-white/10 bg-ink-900/70 p-4 shadow-2xl backdrop-blur-xl md:max-h-[calc(100vh-180px)]"
    >
      <h2 className="mb-3 font-mono text-[10px] uppercase tracking-[0.25em] text-ink-400">Data layers</h2>

      {GROUPS.map((group) => {
        const layers = LAYERS.filter((l) => l.group === group);
        if (!layers.length) return null;
        return (
          <section key={group} className="mb-4 last:mb-0">
            <h3 className="mb-2 text-xs font-semibold text-ink-200">{group}</h3>
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
                          <span key={item.label} className="flex items-center gap-1.5 text-[10px] text-ink-400">
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

      <p className="mt-2 border-t border-white/5 pt-3 text-[10px] leading-relaxed text-ink-400">
        <span className="text-emerald-400">LIVE</span> layers stream from public feeds ·{' '}
        <span className="text-amber-400">SAMPLE</span> layers show real locations with illustrative
        readings pending official adapters. <a href="/methodology" className="text-accent underline-offset-2 hover:underline">Methodology →</a>
      </p>
    </aside>
  );
}
