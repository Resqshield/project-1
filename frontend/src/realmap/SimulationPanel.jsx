import React from "react";

export default function SimulationPanel({
  simulationState,
  simulationVillages,
  originVillage,
  setOriginVillage,
  onMirrorCloudburst,
  onResetSimulation,
  bridgeStatus
}) {
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

      {(simulationState === "ACTIVE" || simulationState === "PARTIAL") && (
        <div style={{ marginBottom: 16, padding: 8, background: "rgba(139,92,246,0.1)", borderRadius: 6, border: "1px dashed rgba(139,92,246,0.3)" }}>
          <div style={{ color: "#fca5a5", fontSize: 12, fontWeight: "bold", marginBottom: 4 }}>
            SIMULATION ONLY — NOT OBSERVED HAZARD
          </div>
          <div style={{ fontSize: 11, color: "#cbd5e1" }}>
            Cloudburst demo — Mandi, Himachal Pradesh
            <br/>
            Affected demo villages: {simulationVillages.length}
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: "#94a3b8", fontStyle: "italic" }}>
            Cloudburst trigger is a hard-coded demo mirror of the external HIMAL-EWS simulation. It is not an observed hazard feed.
          </div>
        </div>
      )}

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
          {simulationState === "LOADING" ? "Resolving..." : "Mirror Cloudburst on Map"}
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
          {["Kataula", "Kamand", "Amehar"].map(name => {
            const v = simulationVillages.find(sv => sv.name.toLowerCase() === name.toLowerCase());
            return (
              <div 
                key={name}
                onClick={() => v && setOriginVillage(v)}
                style={{
                  padding: "4px 8px", background: "rgba(0,0,0,0.3)", borderRadius: 4,
                  border: `1px solid ${originVillage?.name === name ? "#8b5cf6" : "#334155"}`,
                  color: v ? (originVillage?.name === name ? "#c4b5fd" : "#e2e8f0") : "#475569",
                  cursor: v ? "pointer" : "default",
                  opacity: (simulationState === "ACTIVE" || simulationState === "PARTIAL") ? 1 : 0.4
                }}
                title={v ? "Click to set as evacuation origin" : "Village location unavailable from current LGD data"}
              >
                {name} {v ? "" : " (unavailable)"}
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
    </div>
  );
}
