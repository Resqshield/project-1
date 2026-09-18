/**
 * frontend/src/realmap/AdminInfoPanel.jsx
 * =========================================
 * Shows clicked admin feature details with full hierarchy,
 * code, and observation coverage schema.
 */

export default function AdminInfoPanel({ feature, onClose }) {
  if (!feature) return null;
  const p = feature.properties || {};
  const pred = feature.prediction;

  const rows = [
    p.state_name   && { label: "State",      value: p.state_name,       code: p.state_code },
    p.district_name && { label: "District",   value: p.district_name,    code: p.district_code },
    p.subdistrict_name && { label: "Sub-dist", value: p.subdistrict_name, code: p.subdistrict_code },
    p.village_name && { label: "Village", value: p.village_name, code: p.village_code },
  ].filter(Boolean);

  return (
    <div className="info-panel">
      <div className="info-header">
        <span className="info-title">Admin Feature</span>
        <button className="info-close" onClick={onClose}>×</button>
      </div>
      <div className="info-body" style={{ maxHeight: "400px", overflowY: "auto" }}>
        {rows.map(({ label, value, code }) => (
          <div key={label} className="info-row">
            <span className="info-label">{label}</span>
            <div className="info-val-wrap">
              <span className="info-value">{value}</span>
              {code && <span className="info-code">{code}</span>}
            </div>
          </div>
        ))}

        {feature.layerId === "villages-fill" && !pred && (
          <div className="info-loading">Fetching Prediction Contract...</div>
        )}

        {pred && pred.prediction_available && (
          <>
            <div className="info-coverage-title" style={{marginTop: "8px", color:"#e2e8f0"}}>Prediction Contract</div>
            <div className="coverage-grid" style={{gridTemplateColumns: "1fr"}}>
              <div className="cov-item">
                <div className="cov-label">LGD Identity</div>
                <div className="cov-val present">{pred.lgd_ids?.village_code || p.village_code}</div>
              </div>
              <div className="cov-item" style={{display:"flex", gap:"8px"}}>
                <div style={{flex:1}}>
                  <div className="cov-label">Static Susceptibility</div>
                  <div className="cov-val">{pred.static_susceptibility >= 0 ? pred.static_susceptibility.toFixed(4) : "NEEDS_DATA"}</div>
                </div>
                <div style={{flex:1}}>
                  <div className="cov-label">Dynamic Risk</div>
                  <div className={`cov-val ${pred.dynamic_risk < 0 ? "missing" : ""}`}>
                    {pred.dynamic_risk >= 0 ? pred.dynamic_risk.toFixed(4) : "NEEDS_DATA"}
                  </div>
                </div>
              </div>
              <div className="cov-item" style={{display:"flex", gap:"8px"}}>
                <div style={{flex:1}}>
                  <div className="cov-label">Forecast Horizon</div>
                  <div className="cov-val missing">{pred.forecast_horizon}</div>
                </div>
                <div style={{flex:1}}>
                  <div className="cov-label">Model Confidence</div>
                  <div className="cov-val missing">{pred.model_confidence}</div>
                </div>
              </div>
              <div className="cov-item">
                <div className="cov-label">Data Freshness / Observation</div>
                <div className="cov-val">{pred.data_freshness} / {pred.observation_confidence} (Mode: {pred.data_mode})</div>
              </div>
              <div className="cov-item">
                <div className="cov-label">Prediction Timestamp</div>
                <div className="cov-val">{new Date(pred.prediction_timestamp).toLocaleString()}</div>
              </div>
              <div className="cov-item">
                <div className="cov-label">Model Version</div>
                <div className="cov-val">{pred.model_version}</div>
              </div>
            </div>
          </>
        )}
        
        {pred && !pred.prediction_available && (
          <div className="info-error">
            Prediction failed: {pred.reason}
          </div>
        )}

        <div className="info-coverage-title">Observation Coverage</div>
        <div className="coverage-grid">
          {[
            { src: "rain_source",    label: "Rainfall", val: "CHIRPS (pilot regions)" },
            { src: "river_source",   label: "Rivers",   val: "MANUAL_REQUIRED (CWC)" },
            { src: "terrain_source", label: "Terrain",  val: "GLO-30 (partial)" },
            { src: "label_source",   label: "Labels",   val: "NDMA/DFO (district)" },
          ].map(({ src, label, val }) => (
            <div key={src} className="cov-item">
              <div className="cov-label">{label}</div>
              <div className={`cov-val ${val.includes("MANUAL") ? "missing" : "present"}`}>
                {val}
              </div>
            </div>
          ))}
        </div>

        <div className="info-coverage-title">Infrastructure Context</div>
        <div className="coverage-grid" style={{gridTemplateColumns: "1fr"}}>
          <div className="cov-item" style={{display:"flex", gap:"8px"}}>
            <div style={{flex:1}}>
              <div className="cov-label">Nearest Hospital</div>
              <div className="cov-val">
                {pred?.nearest_hospital_m != null ? `${(pred.nearest_hospital_m / 1000).toFixed(2)} km` : "Unknown"}
              </div>
            </div>
            <div style={{flex:1}}>
              <div className="cov-label">Nearest Road</div>
              <div className="cov-val">
                {pred?.nearest_road_m != null ? `${(pred.nearest_road_m / 1000).toFixed(2)} km` : "Unknown"}
              </div>
            </div>
          </div>
        </div>
        <div className="info-disclaimer" style={{color:"#f59e0b", marginTop:"4px"}}>
          Evacuation routing unavailable — verified hospitals/shelters are shown.
        </div>

        <div className="info-disclaimer">
          Research-only. No operational hazard prediction.
        </div>
      </div>

      <style>{`
        .info-panel { margin: 10px 12px; background: rgba(30,41,59,0.95); border: 1px solid rgba(51,65,85,0.5); border-radius: 8px; overflow: hidden; width: 280px; }
        .info-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; border-bottom: 1px solid rgba(51,65,85,0.4); }
        .info-title { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
        .info-close { background: none; border: none; color: #475569; cursor: pointer; font-size: 16px; line-height: 1; padding: 0 2px; }
        .info-close:hover { color: #94a3b8; }
        .info-body { padding: 8px 10px; display: flex; flex-direction: column; gap: 5px; }
        .info-row { display: flex; gap: 8px; align-items: flex-start; }
        .info-label { font-size: 10px; color: #475569; width: 55px; flex-shrink: 0; padding-top: 1px; }
        .info-val-wrap { display: flex; flex-direction: column; gap: 1px; }
        .info-value { font-size: 12px; color: #e2e8f0; font-weight: 500; }
        .info-code { font-size: 9px; color: #475569; font-family: monospace; }
        .info-coverage-title { font-size: 10px; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 8px; margin-bottom: 4px; }
        .coverage-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
        .cov-item { background: rgba(15,23,42,0.5); border-radius: 4px; padding: 5px 6px; border: 1px solid rgba(51,65,85,0.3); }
        .cov-label { font-size: 9px; color: #475569; margin-bottom: 2px; }
        .cov-val { font-size: 10px; font-weight: 500; color: #e2e8f0; }
        .cov-val.present { color: #22c55e; }
        .cov-val.missing  { color: #f59e0b; }
        .info-loading { font-size: 10px; color: #38bdf8; font-style: italic; text-align: center; margin: 4px 0; }
        .info-error { font-size: 10px; color: #ef4444; background: rgba(239,68,68,0.1); padding: 4px; border-radius: 4px; border: 1px solid rgba(239,68,68,0.3); }
        .info-disclaimer { font-size: 9px; color: #334155; text-align: center; margin-top: 4px; }
      `}</style>
    </div>
  );
}
