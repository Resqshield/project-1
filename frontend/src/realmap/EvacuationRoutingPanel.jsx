export default function EvacuationRoutingPanel({ routeStart, routeDest, routeData, onRoute, onClose }) {
  if (!routeDest) return null;

  return (
    <div className="info-panel" style={{ bottom: "auto", top: "20px", right: "20px" }}>
      <div className="info-header">
        <span className="info-title">Evacuation Destination</span>
        <button className="info-close" onClick={onClose}>×</button>
      </div>
      <div className="info-body">
        <div className="info-row">
          <span className="info-label">Facility</span>
          <span className="info-value">{routeDest.properties.name || "Unknown Facility"}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Type</span>
          <span className="info-value">{routeDest.layerId === "evacuation-hospitals" ? "Hospital/Clinic" : "Shelter"}</span>
        </div>

        {routeData && (
          <div className="coverage-grid" style={{ marginTop: "12px", gridTemplateColumns: "1fr" }}>
            <div className="cov-item">
              <div className="cov-label">Distance</div>
              <div className="cov-val present">{(routeData.properties.distance_m / 1000).toFixed(2)} km</div>
            </div>
            <div className="cov-item">
              <div className="cov-label">Travel Time</div>
              <div className="cov-val present">{Math.round(routeData.properties.duration_s / 60)} mins</div>
            </div>
            <div className="cov-item">
              <div className="cov-label">Provider</div>
              <div className="cov-val" style={{ fontSize: "9px" }}>
                {routeData.properties.provider} ({routeData.properties.provenance})
              </div>
            </div>
            <div style={{ color: "#fbbf24", fontSize: "10px", marginTop: "8px", fontStyle: "italic" }}>
              {routeData.properties.warning}
            </div>
          </div>
        )}

        {!routeData && routeStart && (
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
            Select an administrative area (like Mandi) first to route from it.
          </div>
        )}
      </div>
    </div>
  );
}
