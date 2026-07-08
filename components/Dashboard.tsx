'use client';

import { useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useAlerts, useQuakes, useRainfall, useRisk, useRivers } from '@/lib/hooks/useData';
import { useAppStore } from '@/store/useAppStore';
import AlertTicker from '@/components/panels/AlertTicker';
import DetailPanel from '@/components/panels/DetailPanel';
import InfoModal from '@/components/panels/InfoModal';
import LayerToast from '@/components/panels/LayerToast';
import LayerPanel from '@/components/panels/LayerPanel';
import MapDataTable from '@/components/panels/MapDataTable';
import ShortcutsOverlay from '@/components/panels/ShortcutsOverlay';
import Timeline from '@/components/panels/Timeline';
import TopBar from '@/components/panels/TopBar';
import UrlStateSync from '@/components/UrlStateSync';
import { FreshnessBadge } from '@/components/ui/Badge';

// WebGL components are client-only — never server-rendered.
// The loading fallback makes chunk-load failures visible instead of silent.
const MapCanvas = dynamic(() => import('@/components/map/MapCanvas'), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 flex items-center justify-center">
      <span className="rounded-full border border-white/10 bg-ink-900/80 px-4 py-2 font-mono text-xs text-ink-400 backdrop-blur">
        starting map engine…
      </span>
    </div>
  ),
});
const GlobeIntro = dynamic(() => import('@/components/intro/GlobeIntro'), { ssr: false });

/**
 * Dashboard — composition root.
 *
 * The floating UI is split into INDEPENDENT anchored regions (left column,
 * right detail panel, bottom bar) so no panel can push another around:
 * opening the district drill-down never reflows the layer panel.
 */
export default function Dashboard() {
  const introDone = useAppStore((s) => s.introDone);
  const compareDistrictId = useAppStore((s) => s.compareDistrictId);
  const setLayerCollapsed = useAppStore((s) => s.setLayerCollapsed);
  const risk = useRisk();
  const rain = useRainfall();
  const alerts = useAlerts();
  const quakes = useQuakes();
  const rivers = useRivers();

  // R2 — on small landscape phones the top bar + layer panel + bottom bar can
  // consume the whole height; auto-collapse the panel to the icon rail there.
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px) and (orientation: landscape)');
    const apply = () => mq.matches && setLayerCollapsed(true);
    apply();
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, [setLayerCollapsed]);

  return (
    <div className="fixed inset-0 overflow-hidden bg-ink-950">
      {!introDone && <GlobeIntro />}

      <UrlStateSync />

      <MapCanvas
        risk={risk.data}
        rain={rain.data}
        alerts={alerts.data}
        quakes={quakes.data}
        rivers={rivers.data}
      />

      {/* Text alternative to the WebGL map for assistive tech (A2) */}
      <MapDataTable risk={risk.data} rain={rain.data} />

      {/* Left column — brand bar + layer panel (never moves) */}
      <div className="pointer-events-none absolute left-3 right-3 top-3 z-10 flex flex-col gap-3 md:left-4 md:right-auto md:top-4">
        <TopBar />
        <LayerPanel />
      </div>

      {/* Right — district drill-down: side panel on desktop, bottom sheet on
          mobile. A pinned compare panel sits alongside it (X5). */}
      <div className="pointer-events-none absolute inset-x-2 bottom-2 z-20 flex flex-col-reverse gap-2 md:inset-x-auto md:bottom-auto md:right-4 md:top-4 md:flex-row md:items-start">
        {compareDistrictId && (
          <DetailPanel risk={risk.data} rain={rain.data} rivers={rivers.data} mode="compare" />
        )}
        <DetailPanel risk={risk.data} rain={rain.data} rivers={rivers.data} />
      </div>

      {/* Bottom bar — timeline, status, ticker (right inset clears map controls) */}
      <div className="pointer-events-none absolute bottom-3 left-3 right-14 z-10 space-y-2 md:bottom-4 md:left-4 md:right-20">
        <div className="flex flex-col gap-2 md:flex-row md:items-end">
          <div className="md:w-[26rem]">
            <Timeline />
          </div>
          <div className="pointer-events-auto flex items-center gap-3 self-start rounded-lg border border-white/10 bg-ink-900/85 px-3 py-1.5 backdrop-blur-xl md:self-auto">
            <FreshnessBadge updatedAt={rain.updatedAt} error={rain.error} />
            <span className="text-ink-700" aria-hidden>·</span>
            <a href="/methodology" className="font-mono text-[10px] text-ink-400 transition hover:text-accent">
              methodology
            </a>
            <span className="text-ink-700" aria-hidden>·</span>
            <span className="font-mono text-[10px] text-ink-400">
              made by <span className="text-accent/80">AJ</span>
            </span>
          </div>
        </div>
        <AlertTicker alerts={alerts.data} updatedAt={alerts.updatedAt} error={alerts.error} />
      </div>

      <LayerToast />
      <InfoModal />
      <ShortcutsOverlay />
    </div>
  );
}
