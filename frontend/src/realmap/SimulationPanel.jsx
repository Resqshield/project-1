import React, { useState } from "react";
import { HIMAL_EWS_DEMO_VILLAGES } from "./demoVillages.js";

export default function SimulationPanel({
  simulationState,
  simulationVillages,
  originVillage,
  onSelectVillage,
  onMirrorCloudburst,
  onResetSimulation,
  bridgeStatus,
  cloudburstAlert,
  villagePriority
}) {
  const [showDetails, setShowDetails] = useState(false);

  const handleOpenSimulation = (e) => {
    e.preventDefault();
    const resqOrigin = window.location.origin;
    const simulationUrl = "https://himal-ews-v5.vercel.app/?resqOrigin=" + encodeURIComponent(resqOrigin);
    window.open(simulationUrl, "himalEwsSimulation");
  };
  return (
    <div style={{
      position: "absolute",
      bottom: 20,
      left: 20,
      width: 320,
      maxWidth: 340,
      maxHeight: "60vh",
      overflowY: "auto",
      background: "rgba(15,23,42,0.95)",
      border: "1px solid rgba(139,92,246,0.3)",
      borderRadius: 12,
      padding: 16,
      color: "#f8fafc",
      backdropFilter: "blur(12px)",
      zIndex: 10,
      boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      fontFamily: "Inter, sans-serif"
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12
      }}>
        <h3 style={{ margin: 0, fontSize: 16, color: "#c4b5fd" }}>HIMAL-EWS Simulation</h3>
        <span style={{
          fontSize: 10, padding: "2px 6px", borderRadius: 4,
          background: simulationState === "ACTIVE" || simulationState === "PARTIAL" ? "#8b5cf6" :
                      simulationState === "ERROR" ? "#ef4444" : "rgba(255,255,255,0.1)",
          color: simulationState === "IDLE" ? "#94a3b8" : "#fff"
        }}>
          {simulationState}
        </span>
      </div>

      {/* Compact incident card — replaces the old center-map alert */}
      {cloudburstAlert && (
        <div style={{
          marginBottom: 14, padding: "8px 10px", borderRadius: 8,
          background: "rgba(127, 29, 29, 0.18)",
          border: "1px solid rgba(248, 113, 113, 0.55)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "#f8fafc" }}>
            <span style={{ color: "#ef4444" }}>🔴</span>
            <span>
              {cloudburstAlert.unresolved
                ? `CLOUDBURST — UNKNOWN VILLAGE (${cloudburstAlert.village})`
                : `CLOUDBURST — ${cloudburstAlert.village.toUpperCase()}`}
            </span>
          </div>
          {!cloudburstAlert.unresolved && (
            <div style={{ fontSize: 10, fontWeight: 600, color: "#fca5a5", marginTop: 2 }}>
              EVACUATION ACTIVE
            </div>
          )}
          <div style={{ marginTop: 6, fontSize: 10, color: "#e2e8f0", display: "flex", flexDirection: "column", gap: 2 }}>
            {villagePriority && <div>Priority: P{villagePriority}</div>}
            <div>Source: {cloudburstAlert.eventSource === "HIMAL_EWS" ? "HIMAL-EWS EVENT RECEIVED" : "DEV FALLBACK"}</div>
            <div style={{ color: "#fca5a5", fontWeight: 600 }}>SIMULATION ONLY</div>
          </div>
        </div>
      )}

      <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 16, lineHeight: 1.4 }}>
        <strong>External simulation:</strong><br/>
        <a
          href="#"
          onClick={handleOpenSimulation}
          style={{ color: "#60a5fa", textDecoration: "none" }}
        >
          Open Simulation ↗
        </a>
      </div>

      <div style={{ marginBottom: 16, padding: 8, background: "rgba(0,0,0,0.3)", borderRadius: 6, fontSize: 10, border: "1px solid #334155" }}>
        <div style={{ color: "#94a3b8", fontWeight: "bold", marginBottom: 2 }}>HIMAL-EWS bridge:</div>
        <div style={{
          color: bridgeStatus === "WAITING" ? "#fbbf24" : bridgeStatus === "CONNECTED" ? "#34d399" : "#60a5fa",
          marginBottom: 4
        }}>
          {bridgeStatus || "WAITING"}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
        <button
          onClick={onMirrorCloudburst}
          disabled={simulationState !== "IDLE" && simulationState !== "ERROR"}
          style={{
            padding: "8px", background: (simulationState !== "IDLE" && simulationState !== "ERROR") ? "#334155" : "#8b5cf6",
            border: "none", borderRadius: 6, color: "#fff", cursor: (simulationState !== "IDLE" && simulationState !== "ERROR") ? "not-allowed" : "pointer",
            fontWeight: 500, fontSize: 13
          }}
        >
          {simulationState === "LOADING" ? "Resolving..." : "DEV FALLBACK — Mirror Cloudburst on Map"}
        </button>
        <button
          onClick={onResetSimulation}
          disabled={simulationState === "IDLE"}
          style={{
            padding: "8px", background: "transparent",
            border: "1px solid #64748b", borderRadius: 6, color: "#cbd5e1",
            cursor: simulationState === "IDLE" ? "not-allowed" : "pointer",
            fontSize: 13
          }}
        >
          Reset Simulation
        </button>
      </div>

      <div style={{ fontSize: 12, color: "#cbd5e1" }}>
        <strong>Target villages:</strong>
        <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {HIMAL_EWS_DEMO_VILLAGES.map(v => {
            const selected = originVillage?.name === v.name;
            return (
              <div
                key={v.name}
                onClick={() => onSelectVillage(v.name)}
                style={{
                  padding: "4px 8px", background: "rgba(0,0,0,0.3)", borderRadius: 4,
                  border: `1px solid ${selected ? "#8b5cf6" : "#334155"}`,
                  color: selected ? "#c4b5fd" : "#e2e8f0",
                  cursor: "pointer",
                }}
                title="Click to simulate a cloudburst at this village and set it as the evacuation origin"
              >
                {v.name}
              </div>
            );
          })}
        </div>
      </div>

      {(simulationState === "ACTIVE" || simulationState === "PARTIAL") && originVillage && (
        <div style={{ marginTop: 12, fontSize: 12, color: "#10b981" }}>
          Selected evacuation origin: <strong>{originVillage.name}</strong>
        </div>
      )}

      <button
        onClick={() => setShowDetails(d => !d)}
        style={{
          marginTop: 14, background: "transparent", border: "none", padding: 0,
          color: "#7dd3fc", fontSize: 10, fontWeight: 600, cursor: "pointer",
          textDecoration: "underline",
        }}
      >
        {showDetails ? "Hide details" : "Show details"}
      </button>

      {showDetails && (
        <div style={{ marginTop: 10, padding: 8, background: "rgba(139,92,246,0.1)", borderRadius: 6, border: "1px dashed rgba(139,92,246,0.3)" }}>
          <div style={{ color: "#fca5a5", fontSize: 11, fontWeight: "bold", marginBottom: 4 }}>
            SIMULATION ONLY — NOT OBSERVED HAZARD
          </div>
          <div style={{ fontSize: 10, color: "#cbd5e1" }}>
            Cloudburst demo — Mandi, Himachal Pradesh
            <br/>
            Affected demo villages: {simulationVillages.length}
          </div>
          <div style={{ marginTop: 8, fontSize: 9, color: "#94a3b8", fontStyle: "italic" }}>
            Cloudburst trigger is a hard-coded demo mirror of the external HIMAL-EWS simulation. It is not an observed hazard feed. The intended workflow is automatic — click CLOUDBURST inside the open simulation. The dev fallback button above only mirrors it locally.
          </div>
        </div>
      )}
    </div>
  );
}
