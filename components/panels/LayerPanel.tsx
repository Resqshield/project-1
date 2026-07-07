'use client';

import { LAYERS } from '@/lib/layers';
import { useAppStore } from '@/store/useAppStore';
import { TierBadge } from '@/components/ui/Badge';

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
                      className={`group flex w-full items-center gap-2.5 rounded-xl border px-3 py-2 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                        on
                          ? 'border-accent/30 bg-accent/10'
                          : 'border-white/5 bg-white/[0.03] hover:bg-white/[0.07]'
                      }`}
                    >
                      <span
                        aria-hidden
                        className={`relative h-4 w-7 shrink-0 rounded-full transition ${on ? 'bg-accent' : 'bg-ink-700'}`}
                      >
                        <span
                          className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${on ? 'left-3.5' : 'left-0.5'}`}
                        />
                      </span>
                      <span className="flex-1 text-xs text-ink-200">{layer.label}</span>
                      <TierBadge tier={layer.tier} />
                    </button>
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
