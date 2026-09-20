import React from "react";
import { RISK_COLORS } from "./demoVillages.js";

export default function AuthorityCommandPanel({
  demoState,
  fieldAssignments,
  selectedVillage,
  onSelectVillage,
  onUpdateState,
  onAssignField,
  onResetDemo
}) {
  if (!demoState) return null;

  // Convert dictionary to array and sort by priority
  const villages = Object.values(demoState).sort((a, b) => a.priority - b.priority);

  const getColor = (risk_level) => RISK_COLORS[risk_level] || "#94a3b8";

  return (
    <div style={{
      position: "absolute",
      top: 20,
      left: 20,
      width: 320,
      maxHeight: 360,
      overflowY: "auto",
      background: "rgba(15,23,42,0.95)",
      border: "1px solid rgba(239,68,68,0.5)",
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
        <h3 style={{ margin: 0, fontSize: 16, color: "#fca5a5" }}>INCIDENT COMMAND — DEMO</h3>
        <button
          onClick={onResetDemo}
          title="Reset all demo villages, road blocks and field assignments to baseline. Does not touch GloFAS."
          style={{
            padding: "4px 10px", background: "transparent", border: "1px solid #64748b",
            borderRadius: 6, color: "#cbd5e1", fontSize: 10, fontWeight: 600, cursor: "pointer"
          }}
        >
          RESET DEMO
        </button>
      </div>
      
      <div style={{ marginBottom: 16, padding: 8, background: "rgba(239,68,68,0.1)", borderRadius: 6, border: "1px dashed rgba(239,68,68,0.3)" }}>
        <div style={{ color: "#fca5a5", fontSize: 11, fontWeight: "bold", marginBottom: 4 }}>
          SIMULATION / DEMO OPERATIONAL STATE
        </div>
        <div style={{ fontSize: 11, color: "#cbd5e1" }}>
          NOT OBSERVED HAZARD
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
        {villages.map(v => (
          <div 
            key={v.name}
            onClick={() => onSelectVillage(v.name)}
            style={{
              padding: "8px", 
              background: "rgba(0,0,0,0.3)", 
              borderRadius: 6,
              border: `1px solid ${selectedVillage?.name === v.name ? getColor(v.risk_level) : "#334155"}`,
              cursor: "pointer",
              transition: "border 0.2s"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <div style={{ fontSize: 14, fontWeight: "bold" }}>
                <span style={{ color: getColor(v.risk_level), marginRight: 6 }}>●</span>
                {v.name}
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Priority {v.priority}</div>
            </div>
            <div style={{ fontSize: 12, color: getColor(v.risk_level), fontWeight: "bold" }}>
              {v.status}
            </div>
          </div>
        ))}
      </div>

      {selectedVillage && demoState[selectedVillage.name] && (
        <div style={{ marginTop: 16, borderTop: "1px solid #334155", paddingTop: 16 }}>
          <div style={{ fontSize: 14, fontWeight: "bold", marginBottom: 8, color: "#e2e8f0" }}>
            Controls: {selectedVillage.name}
          </div>
          
          {selectedVillage.lat === null || selectedVillage.lon === null ? (
            <div style={{ fontSize: 12, color: "#fbbf24", marginBottom: 12, fontStyle: "italic", lineHeight: 1.4 }}>
              Location pending verification.<br/>EVACUATION ROUTE UNAVAILABLE
            </div>
          ) : null}

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button 
              onClick={() => onUpdateState(selectedVillage.name, "RED", "EVACUATE")}
              style={{
                padding: "8px", background: "#ef4444",
                border: "none", borderRadius: 6, color: "#fff", cursor: "pointer",
                fontWeight: 600, fontSize: 13
              }}
            >
              Issue Evacuation
            </button>
            <button 
              onClick={() => onUpdateState(selectedVillage.name, "ORANGE", "PREPARE")}
              style={{
                padding: "8px", background: "#f97316",
                border: "none", borderRadius: 6, color: "#fff", cursor: "pointer",
                fontWeight: 600, fontSize: 13
              }}
            >
              Set Warning
            </button>
            <button
              onClick={() => onUpdateState(selectedVillage.name, "GREEN", "NORMAL")}
              style={{
                padding: "8px", background: "#22c55e",
                border: "none", borderRadius: 6, color: "#fff", cursor: "pointer",
                fontWeight: 600, fontSize: 13
              }}
            >
              Set Normal
            </button>
            <button
              onClick={() => onAssignField("R04", selectedVillage.name)}
              style={{
                padding: "8px", background: "transparent",
                border: "1px solid #14b8a6", borderRadius: 6, color: "#5eead4", cursor: "pointer",
                fontWeight: 600, fontSize: 13
              }}
            >
              Assign Team R04
            </button>
          </div>

          {fieldAssignments?.R04 && (
            <div style={{ marginTop: 10, fontSize: 11, color: "#94a3b8" }}>
              Team R04 assigned to: <strong style={{ color: "#5eead4" }}>{fieldAssignments.R04.village}</strong>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
