/**
 * frontend/src/realmap/RealAdminMap.jsx
 * =======================================
 * Experimental MapLibre GL JS admin hierarchy map.
 * 
 * RULES:
 *  - EXPERIMENTAL only — not part of synthetic MVP
 *  - NO nationwide hazard predictions
 *  - NO replacement of /api/locations or RiskMap.jsx
 *  - research_only = true label everywhere
 * 
 * ARCHITECTURE:
 *  - Zoom 4-6:  India state boundaries (GeoJSON)
 *  - Zoom 7-9:  District boundaries (GeoJSON)
 *  - Zoom 10+:  Sub-district boundaries (pilot GeoJSON)
 *  - Click: admin info panel (name, code, hierarchy)
 *  - Search: district/state disambiguation
 */

import { useEffect, useRef, useState, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import AdminSearchBar from "./AdminSearchBar.jsx";
import AdminInfoPanel from "./AdminInfoPanel.jsx";
import SimulationPanel from "./SimulationPanel.jsx";
import EvacuationRoutingPanel from "./EvacuationRoutingPanel.jsx";
import AuthorityCommandPanel from "./AuthorityCommandPanel.jsx";
import { HIMAL_EWS_DEMO_VILLAGES, RISK_COLORS, ROUTE_COLORS } from "./demoVillages.js";
import "./RealAdminMap.css";

// Served from backend static or Vite public dir
const GEOJSON_BASE = "/api/real/geojson";

// Fallback: inline pilot GeoJSON served via FastAPI /api/real/geojson/
const LAYERS = {
  states:         { url: `${GEOJSON_BASE}/states_india.geojson`,       zoom: [2,  7] },
  districts:      { url: `${GEOJSON_BASE}/districts_india.geojson`,    zoom: [6, 10] },
  districtsPilot: { url: `${GEOJSON_BASE}/districts_pilot.geojson`,    zoom: [8, 12] },
  subdistricts:   { url: `${GEOJSON_BASE}/subdistricts_pilot.geojson`, zoom: [10, 14] },
};

const PILOT_STATES_BBOX = [67.5, 8.5, 97.5, 35.5]; // India extent

export default function RealAdminMap() {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [selectedFeature, setSelectedFeature] = useState(null);
  const [hoverFeature, setHoverFeature] = useState(null);
  const [zoom, setZoom] = useState(5);
  const [loadStatus, setLoadStatus] = useState({});
  const [error, setError] = useState(null);
  const [layerVisibility, setLayerVisibility] = useState({
    glofas: true,
    hospitals: true,
    shelters: true,
    villages: true,
    landslide: false,
  });
  const [featureCounts, setFeatureCounts] = useState({
    villages: 0,
    evacuation: 0,
    hospitals: 0,
    shelters: 0
  });

  const [routeDest, setRouteDest] = useState(null);
  const [routeData, setRouteData] = useState(null);
  const [routeIssue, setRouteIssue] = useState(null); // "NO_FACILITY" | "NO_ROUTE" | null

  const [demoState, setDemoState] = useState(null);
  const [selectedDemoVillage, setSelectedDemoVillage] = useState(null);

  const [simulationState, setSimulationState] = useState("IDLE"); // IDLE, LOADING, ACTIVE, PARTIAL, ERROR
  const [simulationVillages, setSimulationVillages] = useState([]);
  const [originVillage, setOriginVillage] = useState(null);
  const [bridgeStatus, setBridgeStatus] = useState("WAITING");
  const [cloudburstAlert, setCloudburstAlert] = useState(null);
  const [cloudburstToast, setCloudburstToast] = useState(null);
  const toastTimeoutRef = useRef(null);

  const showCloudburstToast = useCallback((toast) => {
    setCloudburstToast(toast);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = setTimeout(() => setCloudburstToast(null), 4000);
  }, []);

  useEffect(() => () => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
  }, []);

  const villages = demoState?.villages || null;
  const roadBlocks = demoState?.road_blocks || {};
  const fieldAssignments = demoState?.field_assignments || {};

  useEffect(() => {
    const fetchDemoState = async () => {
      try {
        const res = await fetch("/api/demo/state");
        if (res.ok) {
          const data = await res.json();
          setDemoState(data);
        }
      } catch (err) {
        console.warn("Failed to fetch demo state", err);
      }
    };
    fetchDemoState();
    const interval = setInterval(fetchDemoState, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!mapReady || !villages) return;
    const map = mapRef.current;
    if (!map || !map.getSource("src-demo-village-risk")) return;

    const features = [];
    Object.values(villages).forEach(stateObj => {
      const demoV = HIMAL_EWS_DEMO_VILLAGES.find(v => v.name === stateObj.name);
      if (demoV && demoV.lat !== null && demoV.lon !== null) {
        features.push({
          type: "Feature",
          properties: {
            ...demoV,
            ...stateObj
          },
          geometry: {
            type: "Point",
            coordinates: [demoV.lon, demoV.lat]
          }
        });
      }
    });

    map.getSource("src-demo-village-risk").setData({
      type: "FeatureCollection",
      features
    });
  }, [villages, mapReady]);

  // Road blocks (reported by Field Worker) — visible to Authority within the
  // same ~2s poll as demo state.
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;
    const src = map.getSource("src-road-blocks");
    if (!src) return;
    const features = Object.values(roadBlocks).map(b => ({
      type: "Feature",
      properties: { id: b.id, label: b.label, reported_by: b.reported_by },
      geometry: { type: "Point", coordinates: [b.lon, b.lat] },
    }));
    src.setData({ type: "FeatureCollection", features });
  }, [roadBlocks, mapReady]);

  // Pulsing risk halo — DEMO OPERATIONAL RISK OVERLAY, never presented as
  // GloFAS. Pure MapLibre paint-property animation via requestAnimationFrame;
  // no React state/render loop, cleaned up on unmount.
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;
    if (!map.getLayer("demo-village-risk-halo")) return;
    let raf;
    const CYCLE_MS = 2000;
    const tick = (now) => {
      const t = (now % CYCLE_MS) / CYCLE_MS;
      const wave = (Math.sin(t * Math.PI * 2) + 1) / 2; // 0..1, smooth breathing
      const opacity = 0.15 + wave * 0.25; // 0.15 -> 0.40
      const opacityRed = Math.min(0.5, opacity * 1.2); // red pulses slightly stronger
      const radiusMult = 1 + wave * 0.2; // slight expand/contract
      try {
        map.setPaintProperty("demo-village-risk-halo", "circle-opacity", [
          "match", ["get", "risk_level"], "RED", opacityRed, opacity
        ]);
        map.setPaintProperty("demo-village-risk-halo", "circle-radius", [
          "match", ["get", "risk_level"],
          "RED", 30 * radiusMult,
          "ORANGE", 26 * radiusMult,
          "GREEN", 22 * radiusMult,
          22 * radiusMult
        ]);
      } catch {
        // layer may momentarily be gone during style/HMR reloads
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [mapReady]);

  const handleUpdateDemoState = async (name, risk_level, status) => {
    try {
      const endpoint = status === "EVACUATE"
        ? `/api/demo/villages/${encodeURIComponent(name)}/evacuate`
        : `/api/demo/villages/${encodeURIComponent(name)}/risk`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: status === "EVACUATE" ? undefined : JSON.stringify({ risk_level, status })
      });
      if (res.ok) {
        const updated = await res.json();
        setDemoState(prev => prev ? ({ ...prev, villages: { ...prev.villages, [name]: updated } }) : prev);

        if (status === "EVACUATE") {
          const v = HIMAL_EWS_DEMO_VILLAGES.find(x => x.name === name);
          if (v && v.lat !== null && v.lon !== null) {
            setSelectedDemoVillage(v);
            setOriginVillage(v);
            await requestAndDrawEvacuation(v);
          }
        }
      }
    } catch (err) {
      console.warn("Failed to update demo state", err);
    }
  };

  const handleAssignField = async (team, village) => {
    try {
      await fetch("/api/demo/field/assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team, village }),
      });
      setDemoState(prev => prev ? ({
        ...prev,
        field_assignments: { ...prev.field_assignments, [team]: { team, village } },
      }) : prev);
    } catch (err) {
      console.warn("Failed to assign field team", err);
    }
  };

  const handleResetDemo = useCallback(async () => {
    try {
      const res = await fetch("/api/demo/reset", { method: "POST" });
      if (res.ok) setDemoState(await res.json());
    } catch (err) {
      console.warn("Failed to reset demo", err);
    }
    setSimulationState("IDLE");
    setSimulationVillages([]);
    setOriginVillage(null);
    setCloudburstAlert(null);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setCloudburstToast(null);
    setSelectedDemoVillage(null);
    setRouteDest(null);
    setRouteData(null);
    setRouteIssue(null);
    setBridgeStatus("WAITING");
    if (mapRef.current) {
      mapRef.current.getSource("src-simulation")?.setData({ type: "FeatureCollection", features: [] });
      mapRef.current.getSource("src-evacuation-route")?.setData({ type: "FeatureCollection", features: [] });
    }
  }, []);

  const requestEvacuationRoute = useCallback(async (origin, destLat, destLon) => {
    const routeUrl =
      `/api/real/evacuation/route` +
      `?start_lat=${origin.lat}` +
      `&start_lon=${origin.lon}` +
      `&dest_lat=${destLat}` +
      `&dest_lon=${destLon}`;

    const response = await fetch(routeUrl);
    const route = await response.json();

    if (!response.ok || route.error) {
      throw new Error(route.error || `HTTP ${response.status}`);
    }
    if (route.type !== "Feature" || route.geometry?.type !== "LineString") {
      throw new Error("Invalid OSRM route geometry");
    }
    return route;
  }, []);

  const drawEvacuationRoute = useCallback((route, { fit = true } = {}) => {
    const map = mapRef.current;
    if (!map) return;
    const src = map.getSource("src-evacuation-route");
    if (!src) return;

    src.setData(route);
    if (map.getLayer("evacuation-route-casing")) map.moveLayer("evacuation-route-casing");
    if (map.getLayer("evacuation-route")) map.moveLayer("evacuation-route");

    if (!fit) return;
    const coords = route.geometry.coordinates;
    const bounds = coords.reduce(
      (b, coord) => b.extend(coord),
      new maplibregl.LngLatBounds(coords[0], coords[0])
    );
    map.fitBounds(bounds, { padding: { top: 100, bottom: 120, left: 340, right: 80 }, duration: 1000 });
  }, []);

  // Resolve a genuine OSM facility + genuine OSRM route from a village
  // origin and draw it. Single source of truth used by both the Authority
  // "Issue Evacuation" action and the HIMAL-EWS cloudburst handler below.
  const requestAndDrawEvacuation = useCallback(async (origin, { fit = true } = {}) => {
    setRouteIssue(null);
    try {
      const nearestUrl = `/api/real/infrastructure/evacuation/nearest?lat=${origin.lat}&lon=${origin.lon}&radius_km=20`;
      const nearestRes = await fetch(nearestUrl);
      const facility = await nearestRes.json();
      if (facility.error || !facility.geometry) {
        setRouteIssue("NO_FACILITY");
        return;
      }
      const [destLon, destLat] = facility.geometry.coordinates;
      const mappedDest = {
        properties: facility.properties,
        lngLat: { lng: destLon, lat: destLat },
        layerId: facility.properties.amenity === "shelter" ? "evacuation-shelters" : "evacuation-hospitals"
      };
      setRouteDest(mappedDest);

      const route = await requestEvacuationRoute(origin, destLat, destLon);
      setRouteData(route);
      drawEvacuationRoute(route, { fit });
    } catch (err) {
      console.warn("Evacuation routing failed:", err);
      setRouteIssue("NO_ROUTE");
    }
  }, [requestEvacuationRoute, drawEvacuationRoute]);

  // ── Single core handler for a cloudburst event — called identically by
  //    the real HIMAL-EWS postMessage bridge, the local dev fallback, and
  //    manual "Target villages" selection in the SimulationPanel. ────────
  const handleCloudburstEvent = useCallback(async (villageName, meta = {}) => {
    // eventSource distinguishes a REAL externally-received event from a
    // locally-triggered one — never conflate the two in the UI.
    const eventSource = meta.source === "HIMAL_EWS" ? "HIMAL_EWS" : "DEV_FALLBACK";
    const village = HIMAL_EWS_DEMO_VILLAGES.find(
      v => v.name.toLowerCase() === String(villageName || "").toLowerCase()
    );
    if (!village) {
      setSimulationState("ERROR");
      setCloudburstAlert({ village: villageName, timestamp: meta.timestamp || new Date().toISOString(), eventSource, unresolved: true });
      showCloudburstToast({ village: villageName, eventSource, unresolved: true });
      return;
    }

    setSimulationState("ACTIVE");
    setSimulationVillages([village]);
    setOriginVillage(village);
    setSelectedDemoVillage(village);
    setCloudburstAlert({ village: village.name, timestamp: meta.timestamp || new Date().toISOString(), eventSource });
    showCloudburstToast({ village: village.name, eventSource });

    // Only a genuine external HIMAL-EWS message counts as a received bridge
    // event — a dev fallback or manual village pick must never flip this.
    if (eventSource === "HIMAL_EWS") {
      setBridgeStatus("EVENT RECEIVED");
    }

    // Persist to shared demo state so Citizen/Field views pick it up on
    // their next poll — this is what makes the cloudburst "automatic" for
    // every dashboard, not just this tab.
    try {
      const res = await fetch(`/api/demo/villages/${encodeURIComponent(village.name)}/evacuate`, { method: "POST" });
      if (res.ok) {
        const updated = await res.json();
        setDemoState(prev => prev ? ({ ...prev, villages: { ...prev.villages, [village.name]: updated } }) : prev);
      }
    } catch (err) {
      console.warn("Failed to persist cloudburst evacuation state", err);
    }

    if (mapRef.current) {
      mapRef.current.flyTo({ center: [village.lon, village.lat], zoom: 12, duration: 1000 });
    }
    await requestAndDrawEvacuation(village);
  }, [requestAndDrawEvacuation, showCloudburstToast]);

  // DEV FALLBACK ONLY — mirrors a cloudburst locally without the external
  // HIMAL-EWS site. The intended workflow is automatic (see bridge below).
  const handleMirrorCloudburst = useCallback(() => {
    handleCloudburstEvent("Kataula", { timestamp: new Date().toISOString(), source: "DEV_FALLBACK" });
  }, [handleCloudburstEvent]);

  // Manual "Target villages" selection in the SimulationPanel — same single
  // handler as the dev fallback and the real bridge, just a different
  // trigger. Selecting Kataula, Kamand, or Arnehar all go through here.
  const handleSelectDemoVillage = useCallback((name) => {
    handleCloudburstEvent(name, { timestamp: new Date().toISOString(), source: "DEV_FALLBACK" });
  }, [handleCloudburstEvent]);

  // "Reset Simulation" restores full baseline (shared demo state + local
  // simulation UI + bridge status) — same behavior as "Reset Demo", reusing
  // the one reset implementation rather than a second copy.
  const handleResetSimulation = handleResetDemo;

  // ── HIMAL-EWS bridge: exactly one message listener. Only a real message
  //    from the real external origin is ever treated as CONNECTED/received —
  //    opening the popup window does NOT by itself imply connection. ──────
  useEffect(() => {
    const HIMAL_EWS_ORIGIN = "https://himal-ews-v5.vercel.app";
    const handleHimalEvent = (event) => {
      if (event.origin !== HIMAL_EWS_ORIGIN) return;
      const payload = event.data;
      if (payload?.source !== "HIMAL_EWS") return;
      if (payload.type === "CLOUDBURST") {
        handleCloudburstEvent(payload.village, { timestamp: payload.timestamp, source: "HIMAL_EWS" });
      } else if (payload.type === "BRIDGE_INIT") {
        setBridgeStatus("CONNECTED");
      }
    };
    window.addEventListener("message", handleHimalEvent);

    // Dev fallback — calls the SAME handler directly (no postMessage
    // round-trip), so it can never be confused with a real bridge event.
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
      window.__resqTestCloudburst = (village = "Kataula") => {
        handleCloudburstEvent(village, { timestamp: new Date().toISOString(), source: "DEV_FALLBACK" });
      };
    }

    return () => {
      window.removeEventListener("message", handleHimalEvent);
    };
  }, [handleCloudburstEvent]);

  // Keep the active evacuation route current — this is how a road block
  // reported anywhere (Field Worker) reaches the Authority map: the next
  // poll re-requests the route, and the backend reroutes around it.
  useEffect(() => {
    if (!originVillage || !mapReady) return;
    const interval = setInterval(() => {
      requestAndDrawEvacuation(originVillage, { fit: false });
    }, 4000);
    return () => clearInterval(interval);
  }, [originVillage, mapReady, requestAndDrawEvacuation]);

  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    const map = mapRef.current;
    if (map.getSource("src-simulation")) {
      if (simulationState === "ACTIVE" || simulationState === "PARTIAL") {
        const features = simulationVillages.map(v => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [v.lon, v.lat] },
          properties: { name: v.name }
        }));
        map.getSource("src-simulation").setData({ type: "FeatureCollection", features });
      } else {
        map.getSource("src-simulation").setData({ type: "FeatureCollection", features: [] });
      }
    }
  }, [simulationState, simulationVillages, mapReady]);

  useEffect(() => {
    fetch("/api/real/infrastructure/evacuation/summary")
      .then(r => r.json())
      .then(data => {
        setFeatureCounts(prev => ({
          ...prev,
          evacuation: data.total || 0,
          hospitals: data.hospitals || 0,
          shelters: data.shelters || 0
        }));
      })
      .catch(console.warn);

    fetch("/api/real/health")
      .then(r => r.json())
      .then(d => {
        setLoadStatus(prev => ({...prev, health: d.status, version: d.version}));
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    const map = mapRef.current;
    const setVis = (layerId, isVis) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", isVis ? "visible" : "none");
      }
    };
    setVis("glofas-layer", layerVisibility.glofas);
    setVis("evacuation-hospitals", layerVisibility.hospitals);
    setVis("evacuation-shelters", layerVisibility.shelters);
    setVis("villages-fill", layerVisibility.villages);
    setVis("villages-line", layerVisibility.villages);
  }, [layerVisibility, mapReady]);

  // Initialize map
  useEffect(() => {
    if (mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        name: "ResQ Shield Admin Map",
        sources: {
          // CartoDB Dark Matter No Labels — free, no auth, NO city/place labels
          // Eliminates extraneous basemap labels (Vegisir etc.) bleeding through
          "osm-base": {
            type: "raster",
            tiles: [
              "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            ],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
            maxzoom: 19,
          },
        },
        layers: [
          {
            id: "background",
            type: "background",
            paint: { "background-color": "#0d1117" },
          },
          {
            id: "osm-base-layer",
            type: "raster",
            source: "osm-base",
            paint: { "raster-opacity": 0.85 },
          },
        ],
        // MapLibre demo glyphs — free, no key
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      },
      center: [78.9629, 22.5937],
      zoom: 3.8,
      minZoom: 3,
      maxZoom: 14,
    });
    
    map.fitBounds([ [68.0, 8.0], [97.0, 37.0] ], { padding: 20, animate: false });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120 }), "bottom-right");

    map.on("load", async () => {
      // Load all GeoJSON sources
      await loadAllSources(map);
      addAllLayers(map);
      setupInteractions(map);
      setMapReady(true);
    });

    map.on("zoom", () => setZoom(Math.round(map.getZoom() * 10) / 10));
    map.on("error", (e) => {
      const err = e?.error;
      console.error("[MAPLIBRE ERROR MESSAGE]", err?.message);
      console.error("[MAPLIBRE ERROR STATUS]", err?.status);
      console.error("[MAPLIBRE ERROR URL]", err?.url);
      console.error("[MAPLIBRE ERROR STACK]", err?.stack);
      console.error("[MAPLIBRE ERROR RAW]", err);
    });

    mapRef.current = map;
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  const loadAllSources = async (map) => {
    // Initialize all static sources as empty first
    Object.keys(LAYERS).forEach(key => {
      map.addSource(`src-${key}`, { type: "geojson", generateId: true, data: { type: "FeatureCollection", features: [] } });
    });
    
    // Add empty dynamic sources
    map.addSource("src-villages", { type: "geojson", generateId: true, data: { type: "FeatureCollection", features: [] } });
    map.addSource("src-streams", { type: "geojson", generateId: true, data: { type: "FeatureCollection", features: [] } });
    map.addSource("src-catchments", { type: "geojson", generateId: true, data: { type: "FeatureCollection", features: [] } });
    map.addSource("src-demo-village-risk", { type: "geojson", generateId: true, data: { type: "FeatureCollection", features: [] } });

    // Load states synchronously (blocks map rendering)
    console.time("load-states");
    try {
      const resp = await fetch(LAYERS.states.url);
      const geojson = await resp.json();
      map.getSource("src-states").setData(geojson);
      setLoadStatus(prev => ({ ...prev, states: "loaded" }));
    } catch (e) {
      setLoadStatus(prev => ({ ...prev, states: "failed" }));
    }
    console.timeEnd("load-states");

    // Load others asynchronously
    ["districts", "districtsPilot", "subdistricts"].forEach(async (key) => {
      console.time(`load-${key}`);
      try {
        const resp = await fetch(LAYERS[key].url);
        const geojson = await resp.json();
        const source = map.getSource(`src-${key}`);
        if (source) source.setData(geojson);
        setLoadStatus(prev => ({ ...prev, [key]: "loaded" }));
      } catch (e) {
        setLoadStatus(prev => ({ ...prev, [key]: "failed" }));
      }
      console.timeEnd(`load-${key}`);
    });
  };

  const addAllLayers = (map) => {
    // ── State layer ─────────────────────────────────────────────────────────
    map.addLayer({
      id: "states-fill",
      type: "fill",
      source: "src-states",
      minzoom: LAYERS.states.zoom[0],
      maxzoom: LAYERS.states.zoom[1],
      paint: {
        "fill-color": [
          "interpolate", ["linear"], ["zoom"],
          4, "rgba(59, 130, 246, 0.08)",
          7, "rgba(59, 130, 246, 0.04)",
        ],
        "fill-outline-color": "rgba(59, 130, 246, 0.0)",
      },
    });
    
    // ── Demo Village Risk — pulsing halo (DEMO OPERATIONAL RISK OVERLAY,
    //    NEVER the GloFAS inundation extent) + solid center marker ─────────
    map.addSource("src-road-blocks", { type: "geojson", data: { type: "FeatureCollection", features: [] } });

    map.addLayer({
      id: "demo-village-risk-halo",
      type: "circle",
      source: "src-demo-village-risk",
      paint: {
        "circle-radius": 24,
        "circle-color": [
          "match", ["get", "risk_level"],
          "RED", RISK_COLORS.RED,
          "ORANGE", RISK_COLORS.ORANGE,
          "GREEN", RISK_COLORS.GREEN,
          "#94a3b8"
        ],
        "circle-opacity": 0.2,
        "circle-blur": 0.7,
        "circle-stroke-width": 0
      }
    });
    map.addLayer({
      id: "demo-village-risk-layer",
      type: "circle",
      source: "src-demo-village-risk",
      paint: {
        "circle-radius": 10,
        "circle-color": [
          "match",
          ["get", "risk_level"],
          "RED", RISK_COLORS.RED,
          "ORANGE", RISK_COLORS.ORANGE,
          "GREEN", RISK_COLORS.GREEN,
          "#94a3b8"
        ],
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff"
      }
    });
    map.addLayer({
      id: "road-blocks-layer",
      type: "circle",
      source: "src-road-blocks",
      paint: {
        "circle-radius": 8,
        "circle-color": "#f59e0b",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#1c1917"
      }
    });
    map.addLayer({
      id: "states-line",
      type: "line",
      source: "src-states",
      minzoom: LAYERS.states.zoom[0],
      maxzoom: LAYERS.states.zoom[1],
      paint: {
        "line-color": [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          "#60a5fa",
          "#3b82f6",
        ],
        "line-width": [
          "interpolate", ["linear"], ["zoom"],
          4, 0.8, 7, 1.4,
        ],
        "line-opacity": 0.7,
      },
    });
    map.addLayer({
      id: "states-label",
      type: "symbol",
      source: "src-states",
      minzoom: 4,
      maxzoom: 7,
      layout: {
        "text-field": ["get", "state_name"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 4, 9, 6, 12],
        "text-max-width": 8,
        "text-letter-spacing": 0.04,
      },
      paint: {
        "text-color": "#cbd5e1",
        "text-halo-color": "#0d1117",
        "text-halo-width": 2,
      },
    });

    // ── District layer ───────────────────────────────────────────────────────
    map.addLayer({
      id: "districts-fill",
      type: "fill",
      source: "src-districts",
      minzoom: LAYERS.districts.zoom[0],
      maxzoom: LAYERS.districts.zoom[1],
      paint: {
        "fill-color": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          "rgba(251, 191, 36, 0.2)",
          "rgba(34, 197, 94, 0.05)",
        ],
        "fill-outline-color": "rgba(34, 197, 94, 0.0)",
      },
    });
    map.addLayer({
      id: "districts-line",
      type: "line",
      source: "src-districts",
      minzoom: LAYERS.districts.zoom[0],
      maxzoom: LAYERS.districts.zoom[1],
      paint: {
        "line-color": [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          "#86efac",
          "#22c55e",
        ],
        "line-width": [
          "interpolate", ["linear"], ["zoom"],
          6, 0.4, 9, 0.9, 10, 1.2,
        ],
        "line-opacity": 0.5,
      },
    });
    map.addLayer({
      id: "districts-label",
      type: "symbol",
      source: "src-districtsPilot",
      minzoom: 7,
      maxzoom: 11,
      layout: {
        "text-field": ["get", "district_name"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 7, 9, 10, 12],
        "text-max-width": 8,
      },
      paint: {
        "text-color": "#94a3b8",
        "text-halo-color": "#0d1117",
        "text-halo-width": 1.5,
      },
    });

    // ── Sub-district layer ───────────────────────────────────────────────────
    map.addLayer({
      id: "subdistricts-fill",
      type: "fill",
      source: "src-subdistricts",
      minzoom: LAYERS.subdistricts.zoom[0],
      maxzoom: LAYERS.subdistricts.zoom[1],
      paint: {
        "fill-color": [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          "rgba(167, 139, 250, 0.2)",
          "rgba(167, 139, 250, 0.04)",
        ],
        "fill-outline-color": "rgba(0,0,0,0)",
      },
    });
    map.addLayer({
      id: "subdistricts-line",
      type: "line",
      source: "src-subdistricts",
      minzoom: LAYERS.subdistricts.zoom[0],
      maxzoom: LAYERS.subdistricts.zoom[1],
      paint: {
        "line-color": "#a78bfa",
        "line-width": 0.4,
        "line-opacity": 0.4,
      },
    });

    // ── State fill (hover) ─ top of district for state hover ────────────────
    map.addLayer({
      id: "states-fill-hover",
      type: "fill",
      source: "src-states",
      minzoom: LAYERS.states.zoom[0],
      maxzoom: LAYERS.states.zoom[1],
      paint: {
        "fill-color": "rgba(59, 130, 246, 0.15)",
        "fill-opacity": [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          1, 0,
        ],
      },
    });

    // ── Dynamic Catchments ───────────────────────────────────────────────────
    map.addLayer({
      id: "catchments-fill",
      type: "fill",
      source: "src-catchments",
      minzoom: 9,
      paint: {
        "fill-color": "rgba(100, 200, 255, 0.05)",
        "fill-outline-color": "rgba(100, 200, 255, 0.3)",
      },
    });
    map.addLayer({
      id: "catchments-line",
      type: "line",
      source: "src-catchments",
      minzoom: 9,
      paint: {
        "line-color": "#64c8ff",
        "line-width": 0.5,
      },
    });

    // ── Dynamic Streams ──────────────────────────────────────────────────────
    map.addLayer({
      id: "streams-line",
      type: "line",
      source: "src-streams",
      minzoom: 9,
      paint: {
        "line-color": "#3b82f6",
        "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.5, 12, 1.5],
      },
    });

    // ── GloFAS Forecast (WMS) ────────────────────────────────────────────────
    map.addSource("glofas-wms", {
      type: "raster",
      tiles: [
        "https://ows.globalfloods.eu/glofas-ows/ows.py?service=WMS&request=GetMap&layers=FloodHazard100y&styles=&format=image/png&transparent=true&version=1.3.0&width=256&height=256&crs=EPSG:3857&bbox={bbox-epsg-3857}"
      ],
      tileSize: 256,
      attribution: "© Copernicus GloFAS"
    });
    map.addLayer({
      id: "glofas-layer",
      type: "raster",
      source: "glofas-wms",
      paint: { 
        "raster-opacity": 0.85,
        "raster-contrast": 0.2,
        "raster-saturation": 0.5
      },
      layout: { visibility: "visible" }
    });

    // ── Evacuation Points (Hospitals & Shelters) ─────────────────────────────
    map.addSource("evacuation-points", {
      type: "geojson",
      data: "/api/real/infrastructure/evacuation"
    });

    map.addLayer({
      id: "evacuation-hospitals",
      type: "circle",
      source: "evacuation-points",
      filter: ["match", ["get", "amenity"], ["hospital", "clinic"], true, false],
      minzoom: 7,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 2.5, 9, 3, 13, 8],
        "circle-color": "#ef4444",
        "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 7, 0.5, 13, 1],
        "circle-stroke-color": "#ffffff"
      }
    });

    map.addLayer({
      id: "evacuation-shelters",
      type: "circle",
      source: "evacuation-points",
      filter: ["==", ["get", "amenity"], "shelter"],
      minzoom: 7,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 2.5, 9, 3, 13, 8],
        "circle-color": "#22c55e",
        "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 7, 0.5, 13, 1],
        "circle-stroke-color": "#ffffff"
      }
    });

    // Add Evacuation Route layer
    if (!map.getSource("src-evacuation-route")) {
      map.addSource("src-evacuation-route", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });
    }
    
    if (!map.getLayer("evacuation-route-casing")) {
      map.addLayer({
        id: "evacuation-route-casing",
        type: "line",
        source: "src-evacuation-route",
        paint: {
          "line-width": 8,
          "line-color": ROUTE_COLORS.civilian.casing,
          "line-opacity": 1
        }
      });
    }

    if (!map.getLayer("evacuation-route")) {
      map.addLayer({
        id: "evacuation-route",
        type: "line",
        source: "src-evacuation-route",
        paint: {
          "line-width": 5,
          "line-color": ROUTE_COLORS.civilian.core,
          "line-opacity": 1
        }
      });
    }

    // ── Simulation ─────────────────────────────────────────────────────────
    if (!map.getSource("src-simulation")) {
      map.addSource("src-simulation", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });
    }
    if (!map.getLayer("layer-simulation")) {
      map.addLayer({
        id: "layer-simulation",
        type: "circle",
        source: "src-simulation",
        paint: {
          "circle-radius": 9,
          "circle-color": "#d946ef",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff"
        }
      });
    }

    // ── Dynamic Villages ─────────────────────────────────────────────────────
    map.addLayer({
      id: "villages-fill",
      type: "fill",
      source: "src-villages",
      minzoom: 10,
      paint: {
        "fill-color": [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          // Hover state
          "rgba(255, 255, 255, 0.5)", 
          // If we have dynamic risk
          ["all", ["!=", ["feature-state", "dynamic_risk"], null], [">=", ["feature-state", "dynamic_risk"], 0]],
          [
            "interpolate",
            ["linear"],
            ["feature-state", "dynamic_risk"],
            0.0, "rgba(50, 200, 50, 0.1)",   // Low risk
            0.5, "rgba(255, 200, 0, 0.3)",   // Medium risk
            1.0, "rgba(255, 50, 50, 0.5)"    // High risk
          ],
          // Fallback static color
          "rgba(100, 100, 100, 0.05)",
        ],
        "fill-outline-color": "rgba(0,0,0,0)",
      },
    });
    map.addLayer({
      id: "villages-line",
      type: "line",
      source: "src-villages",
      minzoom: 10,
      paint: {
        "line-color": "#ff6464",
        "line-width": 0.5,
      },
    });
  };

  const setupInteractions = (map) => {
    let hoveredId = null;
    let hoveredSource = null;

    const clearHover = () => {
      if (hoveredId != null && hoveredSource) {
        try {
          map.removeFeatureState(
            { source: hoveredSource, id: hoveredId },
            "hover"
          );
        } catch (err) {
          console.warn("[MAP] unable to clear hover state", err);
        }
      }
      hoveredId = null;
      hoveredSource = null;
      setHoverFeature(null);
    };

    const handleMousemove = (e, layerId, sourceId) => {
      if (!e.features?.length) return;
      
      const feature = e.features[0];
      const featureId = feature?.id;
      
      if (featureId == null) {
        // If there's no feature ID, we can't hover state it in MapLibre.
        // It might be missing generateId or promoteId on the source.
        return;
      }
      
      clearHover();
      
      hoveredId = featureId;
      hoveredSource = sourceId;
      
      try {
        map.setFeatureState({ source: sourceId, id: hoveredId }, { hover: true });
      } catch (err) {
        console.warn("[MAP] unable to set hover state", err);
      }
      
      setHoverFeature({
        layer: layerId,
        properties: feature.properties,
      });
      map.getCanvas().style.cursor = "pointer";
    };

    const handleMouseleave = () => {
      clearHover();
      map.getCanvas().style.cursor = "";
    };

    // State interactions
    map.on("mousemove", "states-fill-hover", (e) =>
      handleMousemove(e, "states", "src-states"));
    map.on("mouseleave", "states-fill-hover", handleMouseleave);

    // Demo village click interaction
    map.on("click", "demo-village-risk-layer", (e) => {
      if (!e.features?.length) return;
      const props = e.features[0].properties;
      const villageObj = HIMAL_EWS_DEMO_VILLAGES.find(v => v.name === props.name);
      if (villageObj) {
        setSelectedDemoVillage(villageObj);
        if (villageObj.lat !== null && villageObj.lon !== null) {
          map.flyTo({ center: [villageObj.lon, villageObj.lat], zoom: 12 });
        }
      }
    });
    map.on("mouseenter", "demo-village-risk-layer", () => map.getCanvas().style.cursor = "pointer");
    map.on("mouseleave", "demo-village-risk-layer", () => map.getCanvas().style.cursor = "");

    // District interactions
    map.on("mousemove", "districts-fill", (e) =>
      handleMousemove(e, "districts", "src-districts"));
    map.on("mouseleave", "districts-fill", handleMouseleave);

    // Sub-district interactions
    map.on("mousemove", "subdistricts-fill", (e) =>
      handleMousemove(e, "subdistricts", "src-subdistricts"));
    map.on("mouseleave", "subdistricts-fill", handleMouseleave);

    // Village interactions
    map.on("mousemove", "villages-fill", (e) =>
      handleMousemove(e, "villages", "src-villages"));
    map.on("mouseleave", "villages-fill", handleMouseleave);

    // Viewport Prediction Fetching
    let fetchTimeout = null;
    const updateVillagePredictions = () => {
      if (map.getZoom() < 10) return; // villages not visible
      
      const features = map.queryRenderedFeatures({ layers: ["villages-fill"] });
      const codes = [...new Set(features.map(f => String(f.properties.village_code)))].filter(c => c && c !== "undefined");
      
      if (codes.length === 0) return;
      
      // Batch fetch up to 100 visible villages to avoid massive payloads
      const batchCodes = codes.slice(0, 100);
      
      fetch("/api/real/flood/predict_batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(batchCodes)
      })
      .then(r => r.json())
      .then(data => {
        // Update feature state for Mapbox
        features.forEach(f => {
          const c = String(f.properties.village_code);
          if (data[c]) {
            map.setFeatureState(
              { source: "src-villages", id: f.id },
              { dynamic_risk: data[c].dynamic_risk, static_susceptibility: data[c].static_susceptibility }
            );
          }
        });
      })
      .catch(e => console.error("Batch predict error", e));
    };

    map.on("moveend", () => {
      clearTimeout(fetchTimeout);
      fetchTimeout = setTimeout(updateVillagePredictions, 500); // 500ms debounce
    });

    // Click handlers
    const handleClick = (e) => {
      if (!e.features?.length) return;
      const f = e.features[0];
      const newFeature = { properties: f.properties, lngLat: e.lngLat, layerId: f.layer.id };
      setSelectedFeature(newFeature);

      if (f.layer.id === "villages-fill") {
        const payload = {
          lat: e.lngLat.lat,
          lon: e.lngLat.lng,
          lgd_village_code: String(f.properties.village_code),
          allow_research_imputation: true
        };
        fetch("/api/real/flood/predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        })
          .then(r => r.json())
          .then(data => {
            setSelectedFeature(prev => prev ? { ...prev, prediction: data } : null);
          })
          .catch(console.warn);
      }
    };

    map.on("click", "states-fill-hover", handleClick);
    map.on("click", "districts-fill", handleClick);
    map.on("click", "subdistricts-fill", handleClick);
    map.on("click", "villages-fill", handleClick);

    // Simulation marker popup
    map.on("click", "layer-simulation", (e) => {
      if (!e.features?.length) return;
      const props = e.features[0].properties;
      const coords = e.features[0].geometry.coordinates;
      
      const html = `
        <div style="color: #0f172a; font-family: Inter, sans-serif; font-size: 12px; line-height: 1.4; padding: 4px;">
          <div style="font-weight: bold; color: #8b5cf6; margin-bottom: 6px; font-size: 13px;">HIMAL-EWS SIMULATION</div>
          <div><strong>Village:</strong> ${props.name}</div>
          <div><strong>Event:</strong> Simulated cloudburst</div>
          <div><strong>Source:</strong> Hard-coded demo location</div>
          <div><strong>Observed hazard:</strong> NO</div>
          <div><strong>GloFAS modified:</strong> NO</div>
        </div>
      `;
      
      new maplibregl.Popup({ closeButton: true })
        .setLngLat(coords)
        .setHTML(html)
        .addTo(map);
    });

    map.on("click", "road-blocks-layer", (e) => {
      if (!e.features?.length) return;
      const props = e.features[0].properties;
      const coords = e.features[0].geometry.coordinates;
      const html = `
        <div style="color: #0f172a; font-family: Inter, sans-serif; font-size: 12px; line-height: 1.4; padding: 4px;">
          <div style="font-weight: bold; color: #b45309; margin-bottom: 6px; font-size: 13px;">🚫 REPORTED ROAD BLOCKAGE</div>
          <div><strong>Location:</strong> ${props.label}</div>
          <div><strong>Reported by:</strong> ${props.reported_by}</div>
          <div style="margin-top: 4px; font-style: italic; color: #78716c;">SIMULATION / DEMO field report</div>
        </div>
      `;
      new maplibregl.Popup({ closeButton: true }).setLngLat(coords).setHTML(html).addTo(map);
    });
    map.on("mouseenter", "road-blocks-layer", () => map.getCanvas().style.cursor = "pointer");
    map.on("mouseleave", "road-blocks-layer", () => map.getCanvas().style.cursor = "");

    const handleEvacClick = (e) => {
      if (!e.features?.length) return;
      const f = e.features[0];
      const dest = { properties: f.properties, lngLat: e.lngLat, layerId: f.layer.id };
      setRouteDest(dest);
      setRouteData(null);
      if (map.getSource("src-evacuation-route")) {
        map.getSource("src-evacuation-route").setData({ type: "FeatureCollection", features: [] });
      }
    };
    
    // Add pointer cursor on hover
    const setPointer = () => { map.getCanvas().style.cursor = 'pointer'; };
    const resetPointer = () => { map.getCanvas().style.cursor = ''; };
    
    map.on("mouseenter", "evacuation-hospitals", setPointer);
    map.on("mouseleave", "evacuation-hospitals", resetPointer);
    map.on("mouseenter", "evacuation-shelters", setPointer);
    map.on("mouseleave", "evacuation-shelters", resetPointer);
    map.on("mouseenter", "layer-simulation", setPointer);
    map.on("mouseleave", "layer-simulation", resetPointer);

    map.on("click", "evacuation-hospitals", handleEvacClick);
    map.on("click", "evacuation-shelters", handleEvacClick);

    // Dynamic BBOX loading
    let lastBboxFetch = 0;
    map.on("moveend", () => {
      const now = Date.now();
      if (now - lastBboxFetch < 1000) return;
      lastBboxFetch = now;

      const z = map.getZoom();
      if (z < 9) return;

      const bounds = map.getBounds();
      const min_lon = bounds.getWest();
      const min_lat = bounds.getSouth();
      const max_lon = bounds.getEast();
      const max_lat = bounds.getNorth();
      const q = `?min_lon=${min_lon}&min_lat=${min_lat}&max_lon=${max_lon}&max_lat=${max_lat}`;

      // Also check viewport facilities
      if (z >= 8) {
        const rendered = map.queryRenderedFeatures({ layers: ["evacuation-hospitals", "evacuation-shelters"] });
        setFeatureCounts(prev => ({
          ...prev,
          viewportFacilities: rendered.length
        }));
      } else {
        setFeatureCounts(prev => ({
          ...prev,
          viewportFacilities: -1 // -1 means zoomed out too far to warn
        }));
      }

      fetch(`/api/real/geojson/villages/bbox?min_lon=${min_lon}&min_lat=${min_lat}&max_lon=${max_lon}&max_lat=${max_lat}`);

      if (z >= 10) {
        fetch(`${GEOJSON_BASE}/villages/bbox${q}`)
        .then(r => r.json())
        .then(data => {
          if (map.getSource("src-villages")) {
            map.getSource("src-villages").setData(data);
            setFeatureCounts(prev => ({ ...prev, villages: data.features?.length || 0 }));
          }
        }).catch(console.warn);
      }
      
      fetch(`${GEOJSON_BASE}/streams/bbox${q}`)
        .then(r => r.json())
        .then(data => {
          if (map.getSource("src-streams")) map.getSource("src-streams").setData(data);
        }).catch(console.warn);

      fetch(`${GEOJSON_BASE}/catchments/bbox${q}`)
        .then(r => r.json())
        .then(data => {
          if (map.getSource("src-catchments")) map.getSource("src-catchments").setData(data);
        }).catch(console.warn);
    });
  };

  const handleSelectAdmin = useCallback((res) => {
    // If it's a district/state, maybe we don't have coords. Let's try to fly if lat/lon present.
    if (res.lat && res.lon && mapRef.current) {
      mapRef.current.flyTo({ center: [res.lon, res.lat], zoom: 13 });
    }
  }, []);

  const handleSearchSelect = useCallback((result) => {
    console.log("[Search Diagnostics] Selected result:", result);
    if (!mapRef.current || !result) return;
    const { lat, lon, bbox } = result;
    console.log("[Search Diagnostics] Coordinates to fly to:", { lat, lon, bbox });
    if (bbox) {
      console.log("[Search Diagnostics] Using fitBounds with bbox:", bbox);
      mapRef.current.fitBounds(bbox, { padding: 60, duration: 800 });
    } else if (lat && lon) {
      let targetZoom = 13;
      if (result.type === "state") targetZoom = 6;
      else if (result.type === "district") targetZoom = 9;
      else if (result.type === "subdistrict") targetZoom = 11;
      else if (result.type === "village") targetZoom = 13;
      
      console.log(`[Search Diagnostics] Using flyTo with center: [${lon}, ${lat}], zoom: ${targetZoom}`);
      mapRef.current.flyTo({ center: [lon, lat], zoom: targetZoom, duration: 800 });
    } else {
      console.warn("[Search Diagnostics] WARNING: No valid coordinates (lat/lon) or bbox found in result.");
    }
    setSelectedFeature({ properties: result, lngLat: { lng: lon, lat } });
    
    // Clear existing routing state on new search
    setRouteDest(null);
    setRouteData(null);
    if (mapRef.current && mapRef.current.getSource("src-evacuation-route")) {
      mapRef.current.getSource("src-evacuation-route").setData({ type: "FeatureCollection", features: [] });
    }
  }, []);

  const handleRoute = useCallback(() => {
    const isSimActive = simulationState === "ACTIVE" || simulationState === "PARTIAL";
    const startObj = isSimActive ? originVillage : selectedFeature;
    if (!startObj || !routeDest || !mapRef.current) {
        alert("Please select an origin and a destination first.");
        return;
    }
    
    let start_lat, start_lon;
    if (isSimActive) {
      start_lat = startObj.lat;
      start_lon = startObj.lon;
    } else {
      start_lat = startObj.lngLat.lat;
      start_lon = startObj.lngLat.lng;
    }
    const dest_lat = routeDest.lngLat.lat;
    const dest_lon = routeDest.lngLat.lng;

    setRouteIssue(null);
    fetch(`/api/real/evacuation/route?start_lat=${start_lat}&start_lon=${start_lon}&dest_lat=${dest_lat}&dest_lon=${dest_lon}`)
      .then(r => r.json())
      .then(data => {
        if (data.error || !data.geometry) {
          setRouteIssue("NO_ROUTE");
          return;
        }
        setRouteData(data);
        if (mapRef.current.getSource("src-evacuation-route")) {
          mapRef.current.getSource("src-evacuation-route").setData(data);
          if (data.geometry && data.geometry.coordinates) {
             const coords = data.geometry.coordinates;
             const bounds = coords.reduce((bounds, coord) => {
                return bounds.extend(coord);
             }, new maplibregl.LngLatBounds(coords[0], coords[0]));
             mapRef.current.fitBounds(bounds, { padding: 40 });
          }
        }
      })
      .catch(e => {
        console.error("Routing error", e);
        setRouteIssue("NO_ROUTE");
      });
  }, [selectedFeature, routeDest, simulationState, originVillage]);

  const zoomLabel = zoom < 6 ? "States" : zoom < 9 ? "Districts" : zoom < 12 ? "Sub-districts" : "Village-level (data pending)";

  return (
    <div className="real-admin-map-wrapper">
      {/* Experimental banner */}
      <div className="experimental-banner">
        <span className="banner-badge">REAL PIPELINE</span>
        <span className="banner-text">
          Real admin data & GloFAS WMS. Dynamic risk needs rainfall data.
        </span>
      </div>
      {/* Debug Overlay */}
      <div style={{ position: "absolute", top: 50, left: 10, background: "rgba(15, 23, 42, 0.9)", color: "#10b981", padding: 12, borderRadius: 8, fontSize: 13, fontFamily: "monospace", zIndex: 10, border: "1px solid #334155" }}>
        <div style={{ fontWeight: "bold", marginBottom: 8, color: "#fff" }}>MAP DEBUG STATUS</div>
        <div>Pipeline: <span style={{ color: "#10b981" }}>{loadStatus.version || "REAL (Experimental)"}</span></div>
        <div>Flood (GloFAS): <span style={{ color: "#10b981" }}>LOADED</span></div>
        <div>Landslide: <span style={{ color: "#ef4444" }}>NO_DATA</span></div>
        <div>Evacuation: {featureCounts.evacuation} (H:{featureCounts.hospitals} S:{featureCounts.shelters})</div>
        <div>Route: {routeData ? "READY" : routeDest ? "NOT_REQUESTED" : "NONE"}</div>
        <div>Villages (Viewport): {featureCounts.villages}</div>
        <div>Facilities (Viewport): {featureCounts.viewportFacilities >= 0 ? featureCounts.viewportFacilities : "N/A"}</div>
      </div>

      {/* Layer Toggles */}
      <div style={{ position: "absolute", top: 50, right: 10, background: "rgba(15, 23, 42, 0.9)", color: "#e2e8f0", padding: 12, borderRadius: 8, fontSize: 13, zIndex: 10, border: "1px solid #334155", display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ fontWeight: "bold", marginBottom: 4, color: "#fff" }}>Layers</div>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }} title="Copernicus GloFAS: 100-Year Flood Hazard Extent">
          <input type="checkbox" checked={layerVisibility.glofas} onChange={(e) => setLayerVisibility(p => ({...p, glofas: e.target.checked}))} />
          <span style={{ display: 'inline-block', width: 12, height: 12, background: 'rgba(0, 100, 255, 0.85)', border: '1px solid rgba(0, 100, 255, 1)' }}></span>
          GloFAS 100y Hazard
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input type="checkbox" checked={layerVisibility.hospitals} onChange={(e) => setLayerVisibility(p => ({...p, hospitals: e.target.checked}))} />
          <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#ef4444', border: '1px solid #fff' }}></span>
          Hospitals & Clinics
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input type="checkbox" checked={layerVisibility.shelters} onChange={(e) => setLayerVisibility(p => ({...p, shelters: e.target.checked}))} />
          <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#22c55e', border: '1px solid #fff' }}></span>
          Shelters
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input type="checkbox" checked={layerVisibility.villages} onChange={(e) => setLayerVisibility(p => ({...p, villages: e.target.checked}))} />
          <span style={{ display: 'inline-block', width: 12, height: 12, background: 'rgba(255, 255, 255, 0.2)', border: '1px solid #a78bfa' }}></span>
          Villages
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", opacity: 0.7 }} onClick={(e) => { e.preventDefault(); alert('No verified spatial landslide dataset currently available.'); }}>
          <input type="checkbox" checked={false} readOnly />
          Landslide — NO_DATA
        </label>
      </div>

      <div className="map-layout">
        {/* Sidebar */}
        <div className="map-sidebar">
          <div className="sidebar-header">
            <div className="sidebar-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="3 11 22 2 13 21 11 13 3 11"/>
              </svg>
              Admin Hierarchy
            </div>
            <div className="sidebar-subtitle">India — State → District → Sub-district</div>
          </div>

          <AdminSearchBar onSelect={handleSearchSelect} />

          <div className="sidebar-scroll" style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
            <div className="sidebar-stats">
            <div className="stat-row">
              <span className="stat-label">States / UTs</span>
              <span className="stat-value">41</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Districts</span>
              <span className="stat-value">676</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Sub-districts</span>
              <span className="stat-value">2,347</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Villages</span>
              <span className="stat-value">600,000+</span>
            </div>
          </div>

            <div className="zoom-indicator">
            <div className="zoom-level">Zoom {zoom.toFixed(1)}</div>
            <div className="zoom-layer-label">{zoomLabel}</div>
            <div className="zoom-bar">
              {[
                { label: "States", z: 4 },
                { label: "Districts", z: 7 },
                { label: "Sub-dist", z: 10 },
                { label: "Villages", z: 10 },
              ].map(({ label, z }) => (
                <div
                  key={label}
                  className={`zoom-segment ${zoom >= z ? "active" : ""}`}
                  title={`${label} (zoom ${z}+)`}
                />
              ))}
            </div>
          </div>

          <div className="layer-status">
            {Object.entries(loadStatus).map(([key, status]) => (
              <div key={key} className={`layer-status-row ${status}`}>
                <span className={`status-dot ${status}`} />
                <span className="layer-name">{key}</span>
                <span className="layer-status-text">{status}</span>
              </div>
            ))}
          </div>

          <div className="data-provenance">
            <div className="prov-title">Real Data Provenance</div>
            <div className="prov-row">
              <span className="prov-label">Flood:</span>
              <span className="prov-value">Copernicus GloFAS FloodHazard100y WMS</span>
            </div>
            <div className="prov-row">
              <span className="prov-label">Evacuation:</span>
              <span className="prov-value">OpenStreetMap (Real API)</span>
            </div>
            <div className="prov-row">
              <span className="prov-label">Villages:</span>
              <span className="prov-value">Govt Local Government Directory (LGD)</span>
            </div>
            <div className="prov-row">
              <span className="prov-label">Landslide:</span>
              <span className="prov-value manual">NO_DATA (Pending spatial dataset)</span>
            </div>
          </div>

          {selectedFeature && (
            <AdminInfoPanel
              feature={selectedFeature}
              onClose={() => setSelectedFeature(null)}
            />
          )}
          {routeDest && (
            <EvacuationRoutingPanel
              routeStart={(simulationState === "ACTIVE" || simulationState === "PARTIAL") ? (originVillage ? {properties: {name: originVillage.name}, isSimulation: true} : null) : selectedFeature}
              routeDest={routeDest}
              routeData={routeData}
              routeIssue={routeIssue}
              onRoute={handleRoute}
              onClose={() => {
                setRouteDest(null);
                setRouteData(null);
                setRouteIssue(null);
                if (mapRef.current && mapRef.current.getSource("src-evacuation-route")) {
                  mapRef.current.getSource("src-evacuation-route").setData({ type: "FeatureCollection", features: [] });
                }
              }}
            />
          )}

          {!routeDest && originVillage && routeIssue === "NO_FACILITY" && (
            <div className="info-panel" style={{ bottom: "auto", top: "20px", right: "20px", padding: 16 }}>
              <div style={{ color: "#fca5a5", fontWeight: 700, fontSize: 13 }}>
                NO VERIFIED EVACUATION FACILITY AVAILABLE
              </div>
              <div style={{ color: "#94a3b8", fontSize: 11, marginTop: 4 }}>
                No mapped OSM hospital, clinic or shelter within 20&nbsp;km of {originVillage.name}.
              </div>
            </div>
          )}

          {/* Missing data warning */}
          {featureCounts.viewportFacilities === 0 && zoom >= 8 && (
            <div style={{
              position: "absolute",
              bottom: "40px",
              left: "50%",
              transform: "translateX(-50%)",
              background: "rgba(0, 0, 0, 0.75)",
              color: "#fbbf24",
              padding: "8px 16px",
              borderRadius: "20px",
              fontSize: "13px",
              fontWeight: 500,
              pointerEvents: "none",
              border: "1px solid rgba(251, 191, 36, 0.4)",
              backdropFilter: "blur(4px)"
            }}>
              No verified OSM facilities found in this area.
            </div>
          )}

          </div>
        </div>

      {/* Map */}
        <div className="map-container-wrapper">
          <AuthorityCommandPanel
            demoState={villages}
            fieldAssignments={fieldAssignments}
            selectedVillage={selectedDemoVillage}
            onSelectVillage={(name) => {
              const v = HIMAL_EWS_DEMO_VILLAGES.find(x => x.name === name);
              if (v) {
                setSelectedDemoVillage(v);
                if (v.lat !== null && v.lon !== null && mapRef.current) {
                  mapRef.current.flyTo({ center: [v.lon, v.lat], zoom: 12 });
                }
              }
            }}
            onUpdateState={handleUpdateDemoState}
            onAssignField={handleAssignField}
            onResetDemo={handleResetDemo}
          />
          <SimulationPanel
            simulationState={simulationState}
            simulationVillages={simulationVillages}
            originVillage={originVillage}
            onSelectVillage={handleSelectDemoVillage}
            onMirrorCloudburst={handleMirrorCloudburst}
            onResetSimulation={handleResetSimulation}
            bridgeStatus={bridgeStatus}
            cloudburstAlert={cloudburstAlert}
            villagePriority={cloudburstAlert && !cloudburstAlert.unresolved ? villages?.[cloudburstAlert.village]?.priority : null}
          />
          
          {/* Evacuation Legend */}
          <div style={{
            position: "absolute", bottom: 20, right: 20, background: "rgba(15,23,42,0.9)",
            padding: "10px", borderRadius: "8px", fontSize: "11px", color: "#e2e8f0",
            border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(4px)", zIndex: 10
          }}>
            <div style={{ fontWeight: "bold", marginBottom: "6px", color: "#94a3b8" }}>LEGEND</div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: RISK_COLORS.RED, border: "1px solid #fff" }} />
              <span>Village pulse — DEMO operational state (RED/ORANGE/GREEN)</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#d946ef", border: "1px solid #fff" }} />
              <span>HIMAL-EWS Cloudburst Village</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#f59e0b", border: "1px solid #1c1917" }} />
              <span>Road block — field DEMO report</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444", border: "1px solid #fff" }} />
              <span>OSM Hospital/Clinic (genuine)</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#22c55e", border: "1px solid #fff" }} />
              <span>OSM Shelter (genuine)</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 12, height: 4, background: ROUTE_COLORS.civilian.core }} />
              <span>OSRM Evacuation Route (real routing)</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 12, height: 8, background: "rgba(0, 100, 255, 0.6)" }} />
              <span>GloFAS — genuine hazard layer</span>
            </div>
          </div>

          {/* Cloudburst toast — brief, non-blocking, top-center of the map
              content (below the app header). Never covers the route. */}
          {cloudburstToast && (
            <div
              key={`${cloudburstToast.village}-${cloudburstToast.eventSource}`}
              className="cloudburst-toast"
              style={{
                position: "absolute", top: 54, left: "50%",
                zIndex: 60, maxWidth: 420, width: "max-content",
                display: "flex", alignItems: "center", gap: 10,
                background: "rgba(15,23,42,0.96)", color: "#f8fafc",
                padding: "10px 16px", borderRadius: 8,
                borderLeft: "3px solid #ef4444",
                boxShadow: "0 8px 20px -4px rgba(0,0,0,0.5)",
                backdropFilter: "blur(8px)",
                pointerEvents: "none",
              }}
            >
              <span style={{ fontSize: 16 }}>🚨</span>
              <div style={{ fontSize: 12, lineHeight: 1.4 }}>
                {cloudburstToast.unresolved ? (
                  <span>Cloudburst event received for unknown village <strong>{cloudburstToast.village}</strong></span>
                ) : (
                  <>
                    <div><strong>Cloudburst detected — {cloudburstToast.village}</strong></div>
                    <div style={{ color: "#94a3b8" }}>Evacuation route generated · {cloudburstToast.eventSource === "HIMAL_EWS" ? "HIMAL-EWS" : "DEV FALLBACK"}</div>
                  </>
                )}
              </div>
            </div>
          )}

          <div ref={mapContainerRef} className="maplibre-container" />
          {!mapReady && (
            <div className="map-loading">
              <div className="map-loading-spinner" />
              <div>Loading admin boundaries…</div>
            </div>
          )}
          {hoverFeature && (
            <div className="map-tooltip">
              {hoverFeature.properties.state_name && (
                <div className="tooltip-row">
                  <span className="t-label">State:</span>
                  <span className="t-value">{hoverFeature.properties.state_name}</span>
                </div>
              )}
              {hoverFeature.properties.district_name && (
                <div className="tooltip-row">
                  <span className="t-label">District:</span>
                  <span className="t-value">{hoverFeature.properties.district_name}</span>
                </div>
              )}
              {hoverFeature.properties.subdistrict_name && (
                <div className="tooltip-row">
                  <span className="t-label">Sub-dist:</span>
                  <span className="t-value">{hoverFeature.properties.subdistrict_name}</span>
                </div>
              )}
              {hoverFeature.properties.village_name && (
                <div className="tooltip-row">
                  <span className="t-label">Village:</span>
                  <span className="t-value">{hoverFeature.properties.village_name}</span>
                </div>
              )}
            </div>
          )}
          {error && (
            <div className="map-error">
              <strong>Map error:</strong> {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
