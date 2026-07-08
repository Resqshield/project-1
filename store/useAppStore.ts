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
  /** Replace the whole active-layer set (used by URL hydration). */
  setActiveLayers: (ids: LayerId[]) => void;
  /** Last toggle action — drives the layer toast + map pop-in animation. */
  lastLayerEvent: { id: LayerId; on: boolean; at: number } | null;

  selectedDistrictId: string | null;
  selectDistrict: (id: string | null) => void;

  /** Second, pinned district for side-by-side compare (X5). */
  compareDistrictId: string | null;
  setCompareDistrict: (id: string | null) => void;

  /** River station whose panel row should flash-highlight when its map marker
   *  is clicked (L5 — dedupe popup ⇄ panel). */
  highlightedStationId: string | null;
  highlightStation: (id: string | null) => void;

  /** Timeline position: hours from now (0 = now, up to 72). */
  timelineHour: number;
  setTimelineHour: (h: number) => void;
  timelinePlaying: boolean;
  setTimelinePlaying: (p: boolean) => void;

  layerPanelOpen: boolean;
  setLayerPanelOpen: (open: boolean) => void;
  /** Collapsed = slim vertical icon rail instead of the full panel (L4). */
  layerCollapsed: boolean;
  setLayerCollapsed: (v: boolean) => void;
  toggleLayerCollapsed: () => void;

  infoOpen: boolean;
  setInfoOpen: (open: boolean) => void;

  /** Keyboard-shortcuts help overlay (A5). */
  shortcutsOpen: boolean;
  setShortcutsOpen: (open: boolean) => void;
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
  setActiveLayers: (ids) => set({ activeLayers: new Set(ids) }),

  selectedDistrictId: null,
  selectDistrict: (id) => set({ selectedDistrictId: id, highlightedStationId: null }),

  compareDistrictId: null,
  setCompareDistrict: (id) =>
    set((s) => ({ compareDistrictId: id === s.selectedDistrictId ? null : id })),

  highlightedStationId: null,
  highlightStation: (id) => set({ highlightedStationId: id }),

  timelineHour: 0,
  setTimelineHour: (h) => set({ timelineHour: h }),
  timelinePlaying: false,
  setTimelinePlaying: (p) => set({ timelinePlaying: p }),

  layerPanelOpen: true,
  setLayerPanelOpen: (open) => set({ layerPanelOpen: open }),
  layerCollapsed: false,
  setLayerCollapsed: (v) => set({ layerCollapsed: v }),
  toggleLayerCollapsed: () => set((s) => ({ layerCollapsed: !s.layerCollapsed })),

  infoOpen: false,
  setInfoOpen: (open) => set({ infoOpen: open }),

  shortcutsOpen: false,
  setShortcutsOpen: (open) => set({ shortcutsOpen: open }),
}));
