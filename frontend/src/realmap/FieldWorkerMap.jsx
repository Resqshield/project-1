/**
 * frontend/src/realmap/FieldWorkerMap.jsx
 * ==========================================
 * Field worker view: "Reach the incident safely, verify reality, report
 * ground conditions back to the system." A field team is auto-assigned
 * to whichever village currently has status EVACUATE (falls back to the
 * highest-priority village). Reporting a road block posts it to the
 * shared demo state — the backend's /api/real/evacuation/route then
 * routes around it for every dashboard that re-requests a route.
 */

import { useEffect, useState, useCallback, useRef } from "react";
import { HIMAL_EWS_DEMO_VILLAGES, RISK_COLORS, ROUTE_COLORS } from "./demoVillages.js";
import SimpleDemoMap from "./SimpleDemoMap.jsx";

// Simulated fixed starting position for the demo field team — never called "live GPS".
const TEAM_START = { lat: 31.7119, lon: 76.9327, label: "Mandi town centre" };
const TEAM_NAME = "R04";

export default function FieldWorkerMap() {
  const [demoState, setDemoState] = useState(null);
  const [route, setRoute] = useState(null);
  const [routeIssue, setRouteIssue] = useState(null); // "NO_ROUTE" | null
  const [clickArmed, setClickArmed] = useState(false);
  const [pendingPoint, setPendingPoint] = useState(null);
  const [label, setLabel] = useState("");
  const [statusMsg, setStatusMsg] = useState(null);
  const prevRerouted = useRef(false);

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

  const blockedRoads = demoState?.road_blocks || {};

  // Assigned target: an explicit Authority "ASSIGN TEAM R04" action wins;
  // otherwise fall back to the EVACUATE-status village (or lowest priority).
  const target = (() => {
    if (!demoState) return null;
    const assigned = demoState.field_assignments?.[TEAM_NAME]?.village;
    if (assigned) return HIMAL_EWS_DEMO_VILLAGES.find(v => v.name === assigned) || null;
    const villages = Object.values(demoState.villages || {});
    const evac = villages.find(v => v.status === "EVACUATE");
    const pick = evac || villages.sort((a, b) => a.priority - b.priority)[0];
    if (!pick) return null;
    return HIMAL_EWS_DEMO_VILLAGES.find(v => v.name === pick.name) || null;
  })();
  const targetState = target ? demoState?.villages?.[target.name] : null;

  const fetchRoute = useCallback(async (dest) => {
    try {
      const routeUrl =
        `/api/real/evacuation/route?start_lat=${TEAM_START.lat}&start_lon=${TEAM_START.lon}` +
        `&dest_lat=${dest.lat}&dest_lon=${dest.lon}`;
      const res = await fetch(routeUrl);
      const data = await res.json();
      if (data.error || !data.geometry) {
        setRouteIssue("NO_ROUTE");
        return;
      }
      setRouteIssue(null);
      if (data.properties?.rerouted && !prevRerouted.current) {
        setStatusMsg({ type: "success", text: "✅ ROUTE UPDATED — avoiding reported block." });
        setTimeout(() => setStatusMsg(null), 6000);
      }
      prevRerouted.current = !!data.properties?.rerouted;
      setRoute(data);
    } catch (err) {
      console.warn("Failed to fetch field route", err);
      setRouteIssue("NO_ROUTE");
    }
  }, []);

  useEffect(() => {
    if (!target) { setRoute(null); return; }
    fetchRoute(target);
    const interval = setInterval(() => fetchRoute(target), 4000);
    return () => clearInterval(interval);
  }, [target?.name, fetchRoute]);

  // Snap the clicked point to the nearest vertex of the currently-drawn route.
  // The field worker is reporting a block ON the visible route — at country-wide
  // zoom a raw click can easily land 100s of metres off the line, which the
  // backend would then (correctly) treat as not actually blocking anything.
  const snapToRoute = useCallback((point) => {
    const coords = route?.geometry?.coordinates;
    if (!coords || coords.length === 0) return point;
    let best = coords[0];
    let bestDist = Infinity;
    for (const [lon, lat] of coords) {
      const d = (lat - point.lat) ** 2 + (lon - point.lon) ** 2;
      if (d < bestDist) { bestDist = d; best = [lon, lat]; }
    }
    return { lat: best[1], lon: best[0] };
  }, [route]);

  const handleMapClick = useCallback((point) => {
    setPendingPoint(snapToRoute(point));
    setClickArmed(false);
  }, [snapToRoute]);

  const submitReport = async () => {
    if (!pendingPoint) return;
    try {
      await fetch("/api/demo/road-block", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: pendingPoint.lat,
          lon: pendingPoint.lon,
          label: label.trim() || `Near ${target?.name || "route"}`,
          reported_by: `Team ${TEAM_NAME}`,
        }),
      });
      setPendingPoint(null);
      setLabel("");
      setStatusMsg({ type: "info", text: "🚫 REPORTED ROAD BLOCKAGE — recalculating routes…" });
      if (target) await fetchRoute(target);
    } catch (err) {
      console.warn("Failed to report road block", err);
    }
  };

  const clearOneBlock = async (id) => {
    try {
      await fetch(`/api/demo/road-clear/${id}`, { method: "POST" });
      if (target) await fetchRoute(target);
    } catch (err) {
      console.warn("Failed to clear road block", err);
    }
  };

  const clearBlocks = async () => {
    try {
      await fetch("/api/demo/road-block/reset", { method: "POST" });
      setStatusMsg(null);
      prevRerouted.current = false;
      if (target) await fetchRoute(target);
    } catch (err) {
      console.warn("Failed to reset road blocks", err);
    }
  };

  const markers = [
    { lat: TEAM_START.lat, lon: TEAM_START.lon, color: "#14b8a6", label: `Team ${TEAM_NAME} (demo responder position)` },
  ];
  if (target) {
    markers.push({
      lat: target.lat, lon: target.lon,
      color: RISK_COLORS[targetState?.risk_level] || "#94a3b8",
      label: target.name,
    });
  }
  Object.values(blockedRoads).forEach(b => {
    markers.push({ lat: b.lat, lon: b.lon, color: "#f59e0b", label: `🚫 ${b.label}` });
  });
  if (pendingPoint) {
    markers.push({ lat: pendingPoint.lat, lon: pendingPoint.lon, color: "#fbbf24", label: "New report (unconfirmed)" });
  }

  const fitTo = target ? [[TEAM_START.lon, TEAM_START.lat], [target.lon, target.lat]] : null;

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Sidebar */}
      <div style={{
        width: 320, background: "rgba(15,23,42,0.95)", borderRight: "1px solid rgba(51,65,85,0.5)",
        padding: 16, color: "#f8fafc", display: "flex", flexDirection: "column", gap: 16, overflowY: "auto",
      }}>
        <div style={{
          padding: 10, background: "rgba(20,184,166,0.1)", border: "1px solid rgba(20,184,166,0.3)",
          borderRadius: 8,
        }}>
          <div style={{ fontSize: 13, color: "#5eead4", fontWeight: 700 }}>FIELD OPERATIONS — DEMO</div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>Team {TEAM_NAME} — Ground verification & operations</div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>ASSIGNMENT</div>
          {target ? (
            <div style={{ fontSize: 16, fontWeight: 700 }}>
              Go to <span style={{ color: RISK_COLORS[targetState?.risk_level] }}>{target.name}</span>
              <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 400, marginTop: 2 }}>
                Risk: {targetState?.risk_level || "UNKNOWN"} · Task: {targetState?.status || "UNKNOWN"}
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 13, color: "#64748b" }}>Waiting for assignment…</div>
          )}
        </div>

        {route && (
          <div style={{ fontSize: 12, color: "#cbd5e1", display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{
              alignSelf: "flex-start", padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
              background: route.properties.rerouted ? "rgba(20,184,166,0.2)" : "rgba(255,255,255,0.1)",
              color: route.properties.rerouted ? "#5eead4" : "#e2e8f0",
            }}>
              {route.properties.rerouted ? "ALTERNATIVE ROUTE" : "PRIMARY ROUTE"}
            </span>
            <div>Distance: <strong>{(route.properties.distance_m / 1000).toFixed(1)} km</strong></div>
            <div>ETA: <strong>{Math.round(route.properties.duration_s / 60)} min</strong></div>
            <div style={{ color: "#fbbf24", fontWeight: 600 }}>Route safety: NOT VERIFIED</div>
          </div>
        )}
        {target && !route && routeIssue === "NO_ROUTE" && (
          <div style={{ padding: 8, borderRadius: 6, background: "rgba(239,68,68,0.15)", border: "1px solid #ef4444", color: "#fca5a5", fontSize: 12, fontWeight: 600 }}>
            ROUTING TEMPORARILY UNAVAILABLE
          </div>
        )}

        {statusMsg && (
          <div style={{
            padding: 8, borderRadius: 6, fontSize: 12, fontWeight: 600,
            background: statusMsg.type === "success" ? "rgba(34,197,94,0.15)" : "rgba(59,130,246,0.15)",
            color: statusMsg.type === "success" ? "#86efac" : "#93c5fd",
            border: `1px solid ${statusMsg.type === "success" ? "#22c55e" : "#3b82f6"}`,
          }}>
            {statusMsg.text}
          </div>
        )}

        <div style={{ borderTop: "1px solid #334155", paddingTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 11, color: "#94a3b8" }}>GROUND REPORTING</div>
          {!clickArmed && !pendingPoint && (
            <button
              onClick={() => setClickArmed(true)}
              style={{
                padding: "8px", background: "#ef4444", border: "none", borderRadius: 6,
                color: "#fff", fontWeight: 600, fontSize: 13, cursor: "pointer",
              }}
            >
              Report Road Block
            </button>
          )}
          {clickArmed && (
            <div style={{ fontSize: 12, color: "#fbbf24" }}>
              Click a point on the map to mark the blocked location.
              <button
                onClick={() => setClickArmed(false)}
                style={{ display: "block", marginTop: 6, background: "transparent", border: "1px solid #64748b", borderRadius: 6, color: "#cbd5e1", padding: "4px 8px", cursor: "pointer", fontSize: 11 }}
              >
                Cancel
              </button>
            </div>
          )}
          {pendingPoint && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <input
                type="text"
                placeholder="Optional note (e.g. landslide across road)"
                value={label}
                onChange={e => setLabel(e.target.value)}
                style={{
                  padding: "6px 8px", borderRadius: 6, border: "1px solid #334155",
                  background: "rgba(0,0,0,0.3)", color: "#f8fafc", fontSize: 12,
                }}
              />
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={submitReport}
                  style={{ flex: 1, padding: "6px", background: "#22c55e", border: "none", borderRadius: 6, color: "#fff", fontWeight: 600, fontSize: 12, cursor: "pointer" }}
                >
                  Confirm
                </button>
                <button
                  onClick={() => setPendingPoint(null)}
                  style={{ padding: "6px 10px", background: "transparent", border: "1px solid #64748b", borderRadius: 6, color: "#cbd5e1", fontSize: 12, cursor: "pointer" }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {Object.keys(blockedRoads).length > 0 && (
            <>
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 8 }}>ACTIVE REPORTS</div>
              {Object.values(blockedRoads).map(b => (
                <div key={b.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, fontSize: 11, color: "#fbbf24" }}>
                  <span>🚫 {b.label} — {b.reported_by}</span>
                  <button
                    onClick={() => clearOneBlock(b.id)}
                    title="Clear this road block"
                    style={{ background: "transparent", border: "1px solid #64748b", borderRadius: 4, color: "#cbd5e1", fontSize: 10, padding: "2px 6px", cursor: "pointer" }}
                  >
                    Clear
                  </button>
                </div>
              ))}
              <button
                onClick={clearBlocks}
                style={{ marginTop: 4, padding: "6px", background: "transparent", border: "1px solid #64748b", borderRadius: 6, color: "#cbd5e1", fontSize: 11, cursor: "pointer" }}
              >
                Clear all reported blocks
              </button>
            </>
          )}
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <SimpleDemoMap
          markers={markers}
          route={route}
          routeColor={ROUTE_COLORS.responder}
          fitTo={fitTo}
          onMapClick={handleMapClick}
          clickArmed={clickArmed}
        />
      </div>
    </div>
  );
}
