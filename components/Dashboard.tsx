'use client';

import dynamic from 'next/dynamic';
import { useAlerts, useQuakes, useRainfall, useRisk, useRivers } from '@/lib/hooks/useData';
import { useAppStore } from '@/store/useAppStore';
import AlertTicker from '@/components/panels/AlertTicker';
import DetailPanel from '@/components/panels/DetailPanel';
import InfoModal from '@/components/panels/InfoModal';
import LayerToast from '@/components/panels/LayerToast';
import LayerPanel from '@/components/panels/LayerPanel';
import Timeline from '@/components/panels/Timeline';
import TopBar from '@/components/panels/TopBar';
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
 * Dashboard — composition root. Feeds are fetched once here and flow down to
 * both the map and the panels, so every view of the same data agrees.
 */
export default function Dashboard() {
  const introDone = useAppStore((s) => s.introDone);
  const risk = useRisk();
  const rain = useRainfall();
  const alerts = useAlerts();
  const quakes = useQuakes();
  const rivers = useRivers();

  return (
    <div className="fixed inset-0 overflow-hidden bg-ink-950">
      {!introDone && <GlobeIntro />}

      <MapCanvas risk={risk.data} rain={rain.data} alerts={alerts.data} quakes={quakes.data} rivers={rivers.data} />

      {/* Floating UI — pointer-events pass through the wrapper to the map */}
      <div className="pointer-events-none absolute inset-0 flex flex-col p-3 md:p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 flex-col gap-3 md:flex-none">
            <TopBar />
          </div>
          <div className="hidden md:block">
            <DetailPanel risk={risk.data} rain={rain.data} rivers={rivers.data} />
          </div>
        </div>

        <div className="mt-3 flex min-h-0 flex-1 items-start justify-between gap-3">
          <LayerPanel />
          <div className="md:hidden">
            <DetailPanel risk={risk.data} rain={rain.data} rivers={rivers.data} />
          </div>
        </div>

        <div className="mt-3 space-y-2">
          <div className="flex flex-col gap-2 md:flex-row md:items-end">
            <div className="md:max-w-md md:flex-1">
              <Timeline />
            </div>
            <div className="pointer-events-auto flex items-center gap-3 self-start rounded-lg border border-white/10 bg-ink-900/70 px-3 py-1.5 backdrop-blur-xl md:self-auto">
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
          <AlertTicker alerts={alerts.data} />
        </div>
      </div>

      <LayerToast />
      <InfoModal />
    </div>
  );
}
