/**
 * frontend/src/realmap/TechnicalMap.jsx
 * ========================================
 * Technical / Admin view: "Keep sensors, data sources and GIS/map
 * infrastructure healthy and correct."
 *
 * Two clearly separated concerns, per project data-integrity rules:
 *  1. Real infrastructure health — genuine live checks against the GIS/
 *     GloFAS/OSM/OSRM endpoints. Never invents a status.
 *  2. SIMULATED SENSOR FEED — DEMO — explicitly labeled demo-only values
 *     for the three demo villages. Never called LIVE/OBSERVED/SENSOR
 *     VERIFIED.
 */

import { useEffect, useState } from "react";
import { HIMAL_EWS_DEMO_VILLAGES, RISK_COLORS } from "./demoVillages.js";
import SimpleDemoMap from "./SimpleDemoMap.jsx";

const STATUS_COLOR = {
  AVAILABLE: "#22c55e",
  LOADING: "#94a3b8",
  UNAVAILABLE: "#ef4444",
  UNREACHABLE: "#ef4444",
  NO_DATA: "#f59e0b",
  NOT_CONNECTED: "#f59e0b",
};

function StatusRow({ label, status, detail }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid rgba(51,65,85,0.4)" }}>
      <span style={{ fontSize: 12, color: "#cbd5e1" }}>{label}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {detail && <span style={{ fontSize: 10, color: "#64748b" }}>{detail}</span>}
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: 0.5, padding: "2px 8px", borderRadius: 4,
          color: STATUS_COLOR[status] || "#94a3b8",
          background: `${STATUS_COLOR[status] || "#94a3b8"}22`,
        }}>
          {status.replace(/_/g, " ")}
        </span>
      </span>
    </div>
  );
}

const SENSOR_LABELS = {
  rainfall_channel: "Rainfall channel",
  water_level_trend: "Water-level trend",
  demo_node_health: "Demo node health",
};

export default function TechnicalMap() {
  const [health, setHealth] = useState({
    gis: "LOADING",
    glofas: "LOADING",
    osm: "LOADING",
    osrm: "LOADING",
  });
  const [demoState, setDemoState] = useState(null);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/real/geojson/states_india.geojson")
      .then(r => { if (!cancelled) setHealth(h => ({ ...h, gis: r.ok ? "AVAILABLE" : "UNAVAILABLE" })); })
      .catch(() => { if (!cancelled) setHealth(h => ({ ...h, gis: "UNAVAILABLE" })); });

    // GloFAS is a public WMS raster tile source — check the endpoint responds.
    fetch("https://ows.globalfloods.eu/glofas-ows/ows.py?service=WMS&request=GetCapabilities")
      .then(r => { if (!cancelled) setHealth(h => ({ ...h, glofas: r.ok ? "AVAILABLE" : "UNAVAILABLE" })); })
      .catch(() => { if (!cancelled) setHealth(h => ({ ...h, glofas: "UNAVAILABLE" })); });

    fetch("/api/real/infrastructure/evacuation/summary")
      .then(r => r.json())
      .then(d => { if (!cancelled) setHealth(h => ({ ...h, osm: (d.total || 0) > 0 ? "AVAILABLE" : "UNAVAILABLE" })); })
      .catch(() => { if (!cancelled) setHealth(h => ({ ...h, osm: "UNAVAILABLE" })); });

    fetch("/api/real/routing/health")
      .then(r => r.json())
      .then(d => { if (!cancelled) setHealth(h => ({ ...h, osrm: d.status === "AVAILABLE" ? "AVAILABLE" : "UNAVAILABLE", osrmLatency: d.latency_ms })); })
      .catch(() => { if (!cancelled) setHealth(h => ({ ...h, osrm: "UNAVAILABLE" })); });

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch("/api/demo/state");
        if (res.ok) setDemoState(await res.json());
      } catch (err) {
        console.warn("Failed to fetch demo state", err);
      }
    };
    fetchState();
    const interval = setInterval(fetchState, 2000);
    return () => clearInterval(interval);
  }, []);

  const markers = HIMAL_EWS_DEMO_VILLAGES.map(v => ({
    lat: v.lat, lon: v.lon,
    color: RISK_COLORS[demoState?.villages?.[v.name]?.risk_level] || "#94a3b8",
    label: v.name,
  }));

  return (
    <div style={{ display: "flex", height: "100%", color: "#f8fafc" }}>
      <div style={{ width: 380, background: "rgba(15,23,42,0.95)", borderRight: "1px solid rgba(51,65,85,0.5)", padding: 16, overflowY: "auto", display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#94a3b8", marginBottom: 8, letterSpacing: 0.5 }}>
            DATA & INFRASTRUCTURE HEALTH
          </div>
          <StatusRow label="GIS / admin layers" status={health.gis} />
          <StatusRow label="GloFAS (Copernicus WMS)" status={health.glofas} />
          <StatusRow label="OSM evacuation data" status={health.osm} />
          <StatusRow label="OSRM routing" status={health.osrm} detail={health.osrmLatency ? `${health.osrmLatency} ms` : null} />
          <StatusRow label="Landslide layer" status="NO_DATA" />
          <StatusRow label="Real sensor integration" status="NOT_CONNECTED" />
        </div>

        <div style={{ fontSize: 10, color: "#64748b", lineHeight: 1.5, padding: 10, background: "rgba(0,0,0,0.25)", borderRadius: 8, border: "1px dashed rgba(148,163,184,0.3)" }}>
          Available data ≠ trustworthy observation. GIS/GloFAS/OSM/OSRM above
          are genuine, live-checked infrastructure. No real hardware sensor
          feed is connected to this system — the panel below is explicitly
          simulated.
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#fca5a5", marginBottom: 4, letterSpacing: 0.5 }}>
            SIMULATED SENSOR FEED — DEMO
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 10 }}>
            Not observed hazard. Not LIVE. Not SENSOR VERIFIED.
          </div>
          {HIMAL_EWS_DEMO_VILLAGES.map(v => {
            const sensor = demoState?.sensors?.[v.name];
            return (
              <div key={v.name} style={{ marginBottom: 10, padding: 8, background: "rgba(0,0,0,0.3)", borderRadius: 6, border: "1px solid #334155" }}>
                <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 4 }}>{v.name}</div>
                {sensor ? (
                  Object.entries(sensor).map(([key, val]) => (
                    <div key={key} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#cbd5e1" }}>
                      <span>{SENSOR_LABELS[key] || key}</span>
                      <span style={{ fontWeight: 600 }}>{val.replace(/_/g, " ")}</span>
                    </div>
                  ))
                ) : (
                  <div style={{ fontSize: 11, color: "#64748b" }}>Loading…</div>
                )}
              </div>
            );
          })}
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#94a3b8", marginBottom: 4 }}>PROVENANCE</div>
          <div style={{ fontSize: 10, color: "#94a3b8", lineHeight: 1.6 }}>
            <div>Flood: Copernicus GloFAS FloodHazard100y WMS</div>
            <div>Facilities: OpenStreetMap</div>
            <div>Routing: OSRM / OpenStreetMap</div>
            <div>Villages: Govt Local Government Directory (LGD)</div>
            <div>Arnehar location: SIMULATION_LOCATION_ONLY (see Authority map)</div>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        <div style={{
          position: "absolute", top: 16, left: 16, zIndex: 5, background: "rgba(15,23,42,0.85)",
          padding: "6px 12px", borderRadius: 6, fontSize: 11, color: "#94a3b8", border: "1px solid rgba(51,65,85,0.5)",
        }}>
          Demo village reference — DEMO OPERATIONAL RISK OVERLAY, not GloFAS
        </div>
        <SimpleDemoMap markers={markers} center={[76.9954658, 31.7797769]} zoom={11} />
      </div>
    </div>
  );
}
