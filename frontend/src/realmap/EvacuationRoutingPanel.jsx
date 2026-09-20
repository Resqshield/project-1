export default function EvacuationRoutingPanel({ routeStart, routeDest, routeData, routeIssue, onRoute, onClose }) {
  if (!routeDest) return null;

  const isSim = routeStart?.isSimulation;

  return (
    <div className="info-panel" style={{ bottom: "auto", top: "20px", right: "20px" }}>
      <div className="info-header">
        <span className="info-title">
          {routeData ? "EVACUATION ROUTE — DEMO" : "Evacuation Destination"}
        </span>
        <button className="info-close" onClick={onClose}>×</button>
      </div>
      <div className="info-body">
        {routeStart && (
          <div className="info-row" style={isSim ? { color: "#d946ef", fontWeight: "bold" } : {}}>
            <span className="info-label">{isSim ? "Origin" : "Origin"}</span>
            <span className="info-value">{routeStart.properties.name || "Selected Location"}</span>
          </div>
        )}
        <div className="info-row">
          <span className="info-label">Destination</span>
          <span className="info-value">{routeDest.properties.name || "Unknown Facility"}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Type</span>
          <span className="info-value">{routeDest.layerId === "evacuation-hospitals" || routeDest.properties.amenity === "hospital" || routeDest.properties.amenity === "clinic" ? "Hospital/Clinic" : "Shelter"}</span>
        </div>

        {routeData && (
          <div className="coverage-grid" style={{ marginTop: "12px", gridTemplateColumns: "1fr" }}>
            <span style={{
              alignSelf: "flex-start", padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
              background: routeData.properties.rerouted ? "rgba(20,184,166,0.15)" : "rgba(255,140,0,0.15)",
              color: routeData.properties.rerouted ? "#0d9488" : "#c2410c",
            }}>
              {routeData.properties.rerouted ? "ALTERNATIVE ROUTE" : "PRIMARY ROUTE"}
            </span>
            {routeData.properties.rerouted && (
              <div style={{ marginTop: 6, fontSize: 11, color: "#0d9488", fontWeight: 700 }}>
                🚫 BLOCKAGE REPORTED — ALTERNATIVE ROUTE AVAILABLE
              </div>
            )}
            <div className="cov-item" style={{ marginTop: 8 }}>
              <div className="cov-label">Distance</div>
              <div className="cov-val present">{(routeData.properties.distance_m / 1000).toFixed(1)} km</div>
            </div>
            <div className="cov-item">
              <div className="cov-label">ETA</div>
              <div className="cov-val present">{Math.round(routeData.properties.duration_s / 60)} min</div>
            </div>
            <div className="cov-item">
              <div className="cov-label">Routing</div>
              <div className="cov-val" style={{ fontSize: "9px" }}>
                OSRM / OpenStreetMap
              </div>
            </div>
            <div className="info-row" style={{ marginTop: "8px", borderBottom: "none" }}>
              <span className="info-label">Route safety</span>
              <span className="info-value" style={{ color: "#fbbf24", fontWeight: "bold" }}>NOT VERIFIED</span>
            </div>
            {isSim && (
              <div style={{ color: "#e2e8f0", fontSize: "10px", marginTop: "8px", fontStyle: "italic", lineHeight: 1.4 }}>
                Suggested route to nearest mapped OSM facility.<br/>
                Research/demo routing — not emergency navigation.
              </div>
            )}
          </div>
        )}

        {!routeData && routeIssue === "NO_ROUTE" && (
          <div style={{ marginTop: 12, padding: 8, borderRadius: 6, background: "rgba(239,68,68,0.15)", border: "1px solid #ef4444", color: "#fca5a5", fontSize: 12, fontWeight: 700 }}>
            {isSim ? "NO SAFE ALTERNATIVE FOUND" : "ROUTING TEMPORARILY UNAVAILABLE"}
          </div>
        )}

        {!routeData && routeStart && !isSim && (
          <button 
            className="route-button"
            onClick={onRoute}
            style={{
              marginTop: "12px", width: "100%", padding: "8px",
              background: "#3b82f6", color: "#fff", border: "none",
              borderRadius: "4px", cursor: "pointer", fontWeight: 600
            }}
          >
            Route from {routeStart.properties.name || "Selected Location"}
          </button>
        )}
        
        {!routeData && !routeStart && (
          <div style={{ color: "#94a3b8", fontSize: "11px", marginTop: "12px" }}>
            Select an administrative area (like Mandi) or a Simulation node first to route from it.
          </div>
        )}
      </div>
    </div>
  );
}
