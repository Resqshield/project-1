'use client';

import { useEffect, useState } from 'react';
import { LAYER_BY_ID } from '@/lib/layers';
import { useAppStore } from '@/store/useAppStore';
import { LegendSwatch } from '@/components/panels/LayerPanel';
import LayerIcon from '@/components/ui/LayerIcon';

/**
 * When a layer is toggled, briefly explain what just changed on the map —
 * name, how to read it, and its legend. Announced politely to screen readers.
 */
export default function LayerToast() {
  const event = useAppStore((s) => s.lastLayerEvent);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!event) return;
    setVisible(true);
    const id = setTimeout(() => setVisible(false), 4200);
    return () => clearTimeout(id);
  }, [event]);

  const layer = event ? LAYER_BY_ID.get(event.id) : undefined;
  if (!layer) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`pointer-events-none fixed bottom-28 left-1/2 z-40 w-[min(92vw,26rem)] -translate-x-1/2 transition-all duration-300 ${
        visible ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-3 opacity-0'
      }`}
    >
      <div className="rounded-2xl border border-white/10 bg-ink-900/90 px-4 py-3 shadow-2xl backdrop-blur-xl">
        <p className="flex items-center gap-2 text-xs font-semibold text-white">
          <LayerIcon id={layer.id} active={!!event?.on} />
          {event?.on ? 'Layer added — ' : 'Layer removed — '}
          <span className={event?.on ? 'text-accent' : 'text-ink-400'}>{layer.label}</span>
        </p>
        {event?.on && (
          <>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-400">{layer.description}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
              {layer.legend.map((item) => (
                <span key={item.label} className="flex items-center gap-1.5 text-[10px] text-ink-200">
                  <LegendSwatch color={item.color} shape={item.shape} />
                  {item.label}
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
