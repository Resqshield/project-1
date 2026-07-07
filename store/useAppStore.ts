'use client';

import { create } from 'zustand';
import type { LayerId } from '@/lib/types';
import { LAYERS } from '@/lib/layers';

export type BasemapMode = 'dark' | 'satellite';

interface AppState {
  introDone: boolean;
  finishIntro: () => void;

  basemapMode: BasemapMode;
  setBasemapMode: (m: BasemapMode) => void;

  activeLayers: Set<LayerId>;
  toggleLayer: (id: LayerId) => void;
  /** Last toggle action — drives the layer toast + map pop-in animation. */
  lastLayerEvent: { id: LayerId; on: boolean; at: number } | null;

  selectedDistrictId: string | null;
  selectDistrict: (id: string | null) => void;

  /** Timeline position: hours from now (0 = now, up to 72). */
  timelineHour: number;
  setTimelineHour: (h: number) => void;
  timelinePlaying: boolean;
  setTimelinePlaying: (p: boolean) => void;

  layerPanelOpen: boolean;
  setLayerPanelOpen: (open: boolean) => void;

  infoOpen: boolean;
  setInfoOpen: (open: boolean) => void;
}

const defaultLayers = new Set<LayerId>(LAYERS.filter((l) => l.defaultOn).map((l) => l.id));

export const useAppStore = create<AppState>((set) => ({
  introDone: false,
  finishIntro: () => set({ introDone: true }),

  basemapMode: 'dark',
  setBasemapMode: (m) => set({ basemapMode: m }),

  activeLayers: defaultLayers,
  lastLayerEvent: null,
  toggleLayer: (id) =>
    set((s) => {
      const next = new Set(s.activeLayers);
      const on = !next.has(id);
      if (on) next.add(id);
      else next.delete(id);
      return { activeLayers: next, lastLayerEvent: { id, on, at: Date.now() } };
    }),

  selectedDistrictId: null,
  selectDistrict: (id) => set({ selectedDistrictId: id }),

  timelineHour: 0,
  setTimelineHour: (h) => set({ timelineHour: h }),
  timelinePlaying: false,
  setTimelinePlaying: (p) => set({ timelinePlaying: p }),

  layerPanelOpen: true,
  setLayerPanelOpen: (open) => set({ layerPanelOpen: open }),

  infoOpen: false,
  setInfoOpen: (open) => set({ infoOpen: open }),
}));
