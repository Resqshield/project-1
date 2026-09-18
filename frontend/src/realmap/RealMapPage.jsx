/**
 * frontend/src/realmap/RealMapPage.jsx
 * ======================================
 * Wraps RealAdminMap in a full-page layout accessible
 * via /real-map route. Completely separate from synthetic MVP.
 */

import RealAdminMap from "./RealAdminMap.jsx";

export default function RealMapPage() {
  return (
    <div style={{
      position: "fixed",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      background: "#0f172a",
      fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
    }}>
      {/* Top bar */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 20px",
        background: "rgba(15,23,42,0.95)",
        borderBottom: "1px solid rgba(51,65,85,0.5)",
        flexShrink: 0,
        backdropFilter: "blur(8px)",
        zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 32, height: 32,
            background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
            borderRadius: 8,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                 stroke="white" strokeWidth="2.5">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0", lineHeight: 1.2 }}>
              ResQ Shield
            </div>
            <div style={{ fontSize: 10, color: "#475569" }}>Real Admin Map — Experimental</div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "4px 10px",
            background: "rgba(139,92,246,0.1)",
            border: "1px solid rgba(139,92,246,0.3)",
            borderRadius: 20,
            fontSize: 11, color: "#a78bfa",
          }}>
            <span>⚗</span>
            <span>Research Only</span>
          </div>
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <RealAdminMap />
      </div>
    </div>
  );
}
