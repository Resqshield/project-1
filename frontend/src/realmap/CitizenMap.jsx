/**
 * frontend/src/realmap/CitizenMap.jsx
 * ======================================
 * Citizen-facing view: "See my local danger → where I should go safely."
 * No auth/geolocation system exists in this repo, so the citizen picks
 * which of the three demo villages they're in. Everything else — risk
 * level, evacuation route, reroute-on-road-block — is read live from the
 * same shared demo state the Authority map writes to.
 */

import { useEffect, useState, useCallback, useRef } from "react";
import { HIMAL_EWS_DEMO_VILLAGES, ROUTE_COLORS } from "./demoVillages.js";
import SimpleDemoMap from "./SimpleDemoMap.jsx";

const STATUS_CONFIG = {
  RED: { emoji: "🔴", headline: "EVACUATE NOW", bg: "#7f1d1d", border: "#ef4444" },
  ORANGE: { emoji: "🟠", headline: "WARNING — Be prepared", bg: "#7c2d12", border: "#f97316" },
  GREEN: { emoji: "🟢", headline: "Currently safe", bg: "#14532d", border: "#22c55e" },
};

export default function CitizenMap() {
  const [demoState, setDemoState] = useState(null);
  const [selectedName, setSelectedName] = useState(null);
  const [route, setRoute] = useState(null);
  const [shelter, setShelter] = useState(null);
  const [rerouteBanner, setRerouteBanner] = useState(false);
  const [routeIssue, setRouteIssue] = useState(null); // "NO_FACILITY" | "NO_ROUTE" | null
  const prevRouteDistanceRef = useRef(null);

  // Poll shared demo state, same pattern as RealAdminMap.
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

  const village = HIMAL_EWS_DEMO_VILLAGES.find(v => v.name === selectedName);
  const state = selectedName && demoState ? demoState.villages?.[selectedName] : null;

  const fetchEvacuationRoute = useCallback(async (v) => {
    try {
      const nearestUrl = `/api/real/infrastructure/evacuation/nearest?lat=${v.lat}&lon=${v.lon}&radius_km=20`;
      const nearestRes = await fetch(nearestUrl);
      const facility = await nearestRes.json();
      if (facility.error || !facility.geometry) {
        setRouteIssue("NO_FACILITY");
        return;
      }

      const [destLon, destLat] = facility.geometry.coordinates;
      setShelter({ lat: destLat, lon: destLon, name: facility.properties?.name || "Nearest shelter" });

      const routeUrl =
        `/api/real/evacuation/route?start_lat=${v.lat}&start_lon=${v.lon}` +
        `&dest_lat=${destLat}&dest_lon=${destLon}`;
      const routeRes = await fetch(routeUrl);
      const routeData = await routeRes.json();
      if (routeData.error || !routeData.geometry) {
        setRouteIssue("NO_ROUTE");
        return;
      }
      setRouteIssue(null);

      if (
        prevRouteDistanceRef.current !== null &&
        routeData.properties?.rerouted &&
        prevRouteDistanceRef.current !== routeData.properties.distance_m
      ) {
        setRerouteBanner(true);
        setTimeout(() => setRerouteBanner(false), 8000);
      }
      prevRouteDistanceRef.current = routeData.properties?.distance_m ?? null;
      setRoute(routeData);
    } catch (err) {
      console.warn("Failed to fetch evacuation route", err);
      setRouteIssue("NO_ROUTE");
    }
  }, []);

  // Re-fetch the route whenever the village is RED (poll so a reported
  // road block anywhere in the system reroutes this citizen automatically).
  useEffect(() => {
    if (!village || !state || state.risk_level !== "RED") {
      setRoute(null);
      setShelter(null);
      setRouteIssue(null);
      prevRouteDistanceRef.current = null;
      return;
    }
    fetchEvacuationRoute(village);
    const interval = setInterval(() => fetchEvacuationRoute(village), 4000);
    return () => clearInterval(interval);
  }, [village, state?.risk_level, fetchEvacuationRoute]);

  const cfg = state ? STATUS_CONFIG[state.risk_level] || STATUS_CONFIG.GREEN : null;

  const markers = [];
  if (village) markers.push({ lat: village.lat, lon: village.lon, color: "#3b82f6", label: "You are here" });
  if (shelter) markers.push({ lat: shelter.lat, lon: shelter.lon, color: "#22c55e", label: shelter.name });

  const fitTo = markers.length > 0 ? markers.map(m => [m.lon, m.lat]) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Village picker */}
      <div style={{
        display: "flex", gap: 8, padding: "12px 16px",
        background: "rgba(15,23,42,0.95)", borderBottom: "1px solid rgba(51,65,85,0.5)",
      }}>
        <span style={{ fontSize: 12, color: "#94a3b8", alignSelf: "center", marginRight: 4 }}>
          I am in:
        </span>
        {HIMAL_EWS_DEMO_VILLAGES.map(v => (
          <button
            key={v.name}
            onClick={() => setSelectedName(v.name)}
            style={{
              padding: "6px 14px", borderRadius: 20, fontSize: 13, fontWeight: 600, cursor: "pointer",
              border: `1px solid ${selectedName === v.name ? "#3b82f6" : "#334155"}`,
              background: selectedName === v.name ? "rgba(59,130,246,0.2)" : "rgba(0,0,0,0.3)",
              color: selectedName === v.name ? "#93c5fd" : "#cbd5e1",
            }}
          >
            {v.name}
          </button>
        ))}
      </div>

      {!selectedName ? (
        <div style={{
          flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
          color: "#64748b", fontSize: 14, textAlign: "center", padding: 24,
        }}>
          Select your village above to see your current status.
        </div>
      ) : (
        <>
          {/* Status banner */}
          {cfg && (
            <div style={{
              padding: "20px 16px", background: cfg.bg, borderBottom: `3px solid ${cfg.border}`,
              textAlign: "center",
            }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#fff", letterSpacing: 0.5 }}>
                {cfg.emoji} {cfg.headline}
              </div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.8)", marginTop: 4 }}>
                {selectedName} — updated live from Authority command
              </div>
            </div>
          )}

          {rerouteBanner && (
            <div style={{
              padding: "10px 16px", background: "#78350f", borderBottom: "1px solid #f59e0b",
              color: "#fde68a", fontSize: 13, fontWeight: 600, textAlign: "center",
            }}>
              ⚠️ ROUTE CHANGED — a road on your evacuation route was reported blocked. Use the updated route.
            </div>
          )}

          {state?.risk_level === "RED" && routeIssue === "NO_FACILITY" && (
            <div style={{ padding: "10px 16px", background: "#7f1d1d", color: "#fecaca", fontSize: 13, fontWeight: 600, textAlign: "center" }}>
              NO VERIFIED EVACUATION FACILITY AVAILABLE near {selectedName}.
            </div>
          )}
          {state?.risk_level === "RED" && routeIssue === "NO_ROUTE" && (
            <div style={{ padding: "10px 16px", background: "#7f1d1d", color: "#fecaca", fontSize: 13, fontWeight: 600, textAlign: "center" }}>
              ROUTING TEMPORARILY UNAVAILABLE. Try again shortly.
            </div>
          )}

          {/* Route info */}
          {route && (
            <div style={{
              display: "flex", gap: 24, alignItems: "center", padding: "10px 16px", background: "rgba(15,23,42,0.9)",
              borderBottom: "1px solid rgba(51,65,85,0.5)", fontSize: 12, color: "#e2e8f0",
            }}>
              <span style={{
                padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
                background: route.properties.rerouted ? "rgba(20,184,166,0.2)" : "rgba(255,140,0,0.2)",
                color: route.properties.rerouted ? "#5eead4" : "#ffb366",
              }}>
                {route.properties.rerouted ? "ALTERNATIVE ROUTE" : "PRIMARY ROUTE"}
              </span>
              <span>To: <strong>{shelter?.name}</strong></span>
              <span>Distance: <strong>{(route.properties.distance_m / 1000).toFixed(1)} km</strong></span>
              <span>ETA: <strong>{Math.round(route.properties.duration_s / 60)} min</strong></span>
              <span style={{ color: "#fbbf24", fontWeight: 600 }}>Route safety: NOT VERIFIED</span>
            </div>
          )}

          {/* Map */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <SimpleDemoMap
              markers={markers}
              route={route}
              routeColor={ROUTE_COLORS.civilian}
              fitTo={fitTo}
              center={village ? [village.lon, village.lat] : undefined}
              zoom={13}
            />
          </div>
        </>
      )}

      <div style={{
        padding: "8px 16px", background: "#1e293b", color: "#94a3b8",
        fontSize: 10, textAlign: "center", borderTop: "1px solid rgba(51,65,85,0.5)",
      }}>
        ⚠️ SIMULATION ONLY — NOT AN OBSERVED HAZARD. Not an operational disaster warning system.
      </div>
    </div>
  );
}
