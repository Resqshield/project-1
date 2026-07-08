<div align="center">

# ⛯ Vegvisir

**Real-time disaster intelligence for Kerala & South India**

*Vegvísir — the Norse wayfinder said to guide its bearer through rough weather.*

Live rainfall · hazard alerts · river levels · landslide susceptibility · population exposure · satellite imagery — fused into one immersive, interactive map.

`Next.js 14` · `React 18` · `React Three Fiber` · `MapLibre GL` · `Tailwind CSS` · `TypeScript`

</div>

---

## Table of contents

1. [Features](#features)
2. [Quick start](#quick-start)
3. [Deploying to Vercel](#deploying-to-vercel)
4. [Architecture](#architecture)
5. [Folder structure](#folder-structure)
6. [Data sources & tiers](#data-sources--tiers)
7. [The composite risk index](#the-composite-risk-index)
8. [API reference](#api-reference)
9. [UI & accessibility](#ui--accessibility)
10. [Troubleshooting](#troubleshooting)
11. [Roadmap](#roadmap)
12. [License & attribution](#license--attribution)

---

## Features

- **Cinematic 3D entry** — a photoreal Earth (NASA Blue Marble, terrain bump-mapping, ocean specular, sun-lit terminator, fresnel atmosphere) rotates Kerala into view and dissolves into the live map. Skippable; auto-skipped under `prefers-reduced-motion`.
- **Two basemap modes** — *Dark* (CARTO Dark Matter vector, tuned for data overlays) and *Satellite* (Esri World Imagery — photoreal, Google-Earth-style). Switch any time from the top bar; all overlays survive the swap.
- **Live hazard layers** — district risk choropleth, rainfall (observed + 72 h forecast with a playable timeline), GDACS hazard alerts, USGS earthquakes, NASA GIBS daily satellite overlay.
- **District drill-down** — click any district for an animated risk ring, driver breakdown (rain / landslide / flood / exposure), hourly rainfall sparkline synced to the timeline, and river-gauge status.
- **Honest data tiers** — every layer is badged **LIVE** (streaming from public feeds) or **SAMPLE** (real locations, illustrative readings pending official adapters). Freshness badges report feed age; failures degrade gracefully instead of showing stale data as current.
- **Transparent risk model** — the composite index weights are published at `/methodology` for audit.

## Quick start

**Prerequisites:** Node.js 18.17+ (20+ recommended) and npm.

```bash
git clone <your-repo-url> vegvisir   # or just cd into the project folder
cd vegvisir
npm install
npm run fetch:data                   # optional — bundles district boundaries locally
npm run dev                          # → http://localhost:3000
```

No API keys. No environment variables. Every data source is free and public.

| Script | What it does |
|---|---|
| `npm run dev` | Development server with hot reload |
| `npm run build` | Production build (fails on TypeScript errors) |
| `npm start` | Serve the production build |
| `npm run typecheck` | Type-check without emitting |
| `npm run fetch:data` | Download district boundary GeoJSON into `public/data/` |

## Deploying to Vercel

**Option A — CLI:** `npx vercel` from the project root. Accept the defaults; Vercel auto-detects Next.js.

**Option B — Git:** push to GitHub/GitLab and import the repo at [vercel.com/new](https://vercel.com/new). Zero configuration required.

Recommended (optional): set **Build Command** to `npm run fetch:data && next build` so district boundaries are bundled at build time instead of fetched at runtime.

API routes deploy as serverless functions with edge caching (`s-maxage` + `stale-while-revalidate`) — a cold feed never blocks a user; they get the cached copy while revalidation happens in the background.

## Architecture

```
Browser
  ├── React UI (glass panels) ← zustand store → user intent
  ├── MapLibre GL  — WebGL basemap + 10 overlay layers
  ├── React Three Fiber — photoreal globe intro
  │
  ├── fetch → Next.js API routes (CORS-free proxies, edge-cached)
  │     ├── /api/rainfall   Open-Meteo, all 14 districts in one request (15 min)
  │     ├── /api/risk       composite index, recomputed from live rain (15 min)
  │     ├── /api/alerts     GDACS RSS → normalized alerts (5 min)
  │     └── /api/quakes     USGS, bbox-filtered to peninsular India (5 min)
  │
  └── direct tile streams (no proxy needed)
        ├── CARTO Dark Matter / Esri World Imagery basemaps
        └── NASA GIBS VIIRS true-colour overlay
```

**Five design principles**

1. **Boot instantly, upgrade progressively.** The map constructs with an inline style (zero network dependency for first paint), then swaps in the polished vector basemap when its fetch completes. District markers are seeded before any feed arrives — the map is never blank.
2. **Ingest-and-own.** The browser never talks to fragile upstream feeds directly; API routes normalize, cache, and degrade gracefully.
3. **One-way data loop.** Feeds flow into the map through `setData()`/feature-state; clicks flow out through the store. The WebGL canvas never re-renders with React.
4. **Style-swap-safe overlays.** Every `style.load` event re-attaches all overlay sources/layers idempotently and bumps an epoch counter that re-runs data effects — so switching Dark ↔ Satellite never loses a layer.
5. **Honest tiers.** Real data is never mixed silently with sample data; the UI labels both.

## Folder structure

```
app/
  layout.tsx             fonts, metadata, MapLibre CSS, skip-link
  page.tsx               → Dashboard
  icon.svg               favicon — vegvísir wayfinder mark
  globals.css            Tailwind, MapLibre re-skin, reduced-motion
  methodology/page.tsx   published risk model & source documentation
  api/                   rainfall / risk / alerts / quakes route handlers
components/
  Dashboard.tsx          composition root — feeds fetched once, shared by all
  intro/GlobeIntro.tsx   R3F photoreal Earth, 3-phase cinematic camera
  map/MapCanvas.tsx      MapLibre instance + overlay orchestration
  panels/                TopBar, LayerPanel, DetailPanel, Timeline, AlertTicker
  ui/Badge.tsx           LIVE/SAMPLE + freshness badges
lib/
  types.ts               domain model
  districts.ts           14 districts: centroids, density, susceptibility
  risk.ts                composite risk engine (documented weights)
  layers.ts              layer registry — single source of truth for the panel
  geo.ts                 boundary fetch with multi-source fallback
  sampleData.ts          SAMPLE-tier gauges & facilities
  hooks/useData.ts       polling hooks (pause when the tab is hidden)
  server/rainfall.ts     shared Open-Meteo fetcher
store/useAppStore.ts     zustand: layers, basemap mode, selection, timeline
scripts/fetch-data.mjs   optional boundary bundler
```

## Data sources & tiers

| Layer | Source | Tier | Refresh |
|---|---|---|---|
| Rainfall (obs + 72 h) | [Open-Meteo](https://open-meteo.com) (CC-BY 4.0) | **LIVE** | 15 min |
| Composite risk index | computed from live rain × static factors | **LIVE** | 15 min |
| Hazard alerts | [GDACS](https://gdacs.org) (EC JRC / UN OCHA) | **LIVE** | 5 min |
| Earthquakes | [USGS](https://earthquake.usgs.gov) | **LIVE** | 5 min |
| Satellite overlay | [NASA GIBS](https://earthdata.nasa.gov) VIIRS | **LIVE** | daily |
| Dark basemap | [CARTO Dark Matter](https://carto.com/basemaps) / © OpenStreetMap | LIVE | — |
| Satellite basemap | Esri World Imagery (© Esri, Maxar, Earthstar) | LIVE | — |
| District boundaries | community GeoJSON (datameet lineage) | static | — |
| River discharge | [GloFAS via Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) at CWC station sites | **LIVE** | hourly poll, daily model |
| Hospitals & shelters | real facilities, curated subset | **SAMPLE** | — |
| Landslide susceptibility | derived from NRSC/ISRO Landslide Atlas rankings | static | — |

## The composite risk index

```
risk = 0.40 · rain        (observed 24 h + forecast 48 h, normalized at 250 mm)
     + 0.25 · landslide   (NRSC susceptibility × rain amplification)
     + 0.25 · flood       (historical proneness × rain amplification)
     + 0.10 · exposure    (population density, normalized at 1600 /km²)

amplification = 0.25 + 0.75 · rain-normalized
severity: 0–24 Normal · 25–44 Watch · 45–64 Alert · 65+ Severe
```

Terrain factors are rain-amplified because a susceptible slope is chiefly dangerous while it rains. Weights are deliberately public (`/methodology`) so the model can be audited. **Calibrate against the 2018/2019 Kerala flood record before any operational use.**

## API reference

All routes return `{ updatedAt, tier, source, data }` and cache at the edge.

| Route | Returns | Cache |
|---|---|---|
| `GET /api/rainfall` | `RainPoint[]` — per-district past 24 h, next 24/48/72 h, 72-entry hourly series | 15 min |
| `GET /api/risk` | `RiskScore[]` — score 0–100, severity band, driver breakdown | 15 min |
| `GET /api/alerts` | `HazardAlert[]` — normalized GDACS events for the region | 5 min |
| `GET /api/quakes` | `Quake[]` — USGS events, bbox 66–92°E / 2–22°N | 5 min |

Failures return `502` with a reason; the UI shows per-layer "source unavailable" badges rather than breaking.

## UI & accessibility

Keyboard-navigable controls with visible focus rings · `role="switch"` layer toggles · `aria-pressed` basemap buttons · skip-to-map link · native range input for the timeline (arrow-key scrubbing) · severity colours reserved exclusively for hazard levels (IMD-consistent) with colour-blind-conscious encodings elsewhere · full `prefers-reduced-motion` support (intro skipped, marquee stopped, transitions minimized) · responsive single-column reflow on mobile.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Map area is blank | Open DevTools → Console and look for `[vegvisir]` messages. The boot style needs only `tile.openstreetmap.org` reachable; corporate proxies/adblockers sometimes block tile hosts. |
| "starting map engine…" never clears | The MapLibre chunk failed to load — hard-refresh (Ctrl+Shift+R); if persistent, delete `.next/` and restart `npm run dev`. |
| Intro globe is plain blue | Earth textures stream from `unpkg.com`; if blocked, the intro degrades intentionally. |
| Rainfall circles invisible | It's dry at the selected hour — scrub the timeline; circle size/opacity encode mm/h intensity. |
| No alerts on the map | GDACS may have no active events near South India (a good day). The ticker hides when empty. |
| District polygons missing (dots instead) | Boundary GeoJSON unreachable — run `npm run fetch:data` to bundle it locally. |

## Roadmap

**Data:** NDMA SACHET CAP adapter → IMD official API → CWC live river levels → INCOIS coastal hazards → NRSC Bhuvan WMS zonation → WorldPop exposure rasters.
**Platform:** PostGIS + vector tiles at data scale, WebSocket alert push, Malayalam i18n, historical event archive (2018/2019 flood footprints), PWA offline mode for field responders.
See `vegvisir-implementation-plan.md` for the full phased plan.

## License & attribution

MIT. Basemaps and data feeds retain their own licenses — keep the map attribution control visible (OpenStreetMap contributors, CARTO, Esri, NASA, Open-Meteo CC-BY, GDACS, USGS).

> **Disclaimer:** Vegvisir is a visualization and decision-support layer. Official warnings come from IMD, NDMA and state disaster management authorities.
