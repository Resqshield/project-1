/**
 * frontend/src/realmap/demoVillages.js
 * =====================================
 * Shared static reference data for the three HIMAL-EWS demo villages.
 * Mutable state (risk_level / status / priority) lives server-side in
 * backend/main.py `demo_shared_state`, fetched live via GET /api/demo/state.
 */

export const HIMAL_EWS_DEMO_VILLAGES = [
  {
    name: "Kataula",
    district: "Mandi",
    state: "Himachal Pradesh",
    lat: 31.79778,
    lon: 77.01840,
    coordinateSource: "OpenStreetMap-backed public map reference",
    dataRole: "SIMULATION_LOCATION_ONLY",
    coordinateStatus: "VERIFIED"
  },
  {
    name: "Kamand",
    district: "Mandi",
    state: "Himachal Pradesh",
    lat: 31.78172,
    lon: 76.99736,
    coordinateSource: "OpenStreetMap-backed public map reference",
    dataRole: "SIMULATION_LOCATION_ONLY",
    coordinateStatus: "VERIFIED"
  },
  {
    name: "Arnehar",
    district: "Mandi",
    state: "Himachal Pradesh",
    lat: 31.7797769,
    lon: 76.9954658,
    coordinateSource: "Demo visualization point near OSM way \"Salgi-Arnehar Road\" — no verified LGD/OSM village node exists for Arnehar itself",
    dataRole: "SIMULATION_LOCATION_ONLY",
    coordinateStatus: "DEMO_ONLY"
  }
];

export const HIMAL_EWS_DEMO_VILLAGE_NAMES = HIMAL_EWS_DEMO_VILLAGES.map(v => v.name);

// Shared operational-risk color language (SIMULATION / DEMO OPERATIONAL STATE,
// not observed flood risk). Used by every dashboard so the four maps read as
// one visual system.
export const RISK_COLORS = {
  RED: "#ff2d2d",
  ORANGE: "#ff9800",
  GREEN: "#22c55e",
};

// Civilian evacuation route vs. field-responder route — kept visually
// distinct from each other and from the GloFAS blue hazard layer.
export const ROUTE_COLORS = {
  civilian: { core: "#ff8c00", casing: "#ffffff" },
  responder: { core: "#14b8a6", casing: "#ffffff" },
};
