import { MapPin, Droplets, Mountain, Activity, Wind, Thermometer, TrendingUp, BarChart2 } from 'lucide-react';

/**
 * Returns a CSS class name for a risk level string.
 * Only used for visual styling — risk comes from the backend.
 */
export function getRiskClass(risk) {
  if (!risk) return 'risk-unknown';
  switch (risk.toLowerCase()) {
    case 'high':   return 'risk-high';
    case 'medium': return 'risk-medium';
    case 'low':    return 'risk-low';
    default:       return 'risk-unknown';
  }
}

function RiskSection({ label, risk, probability, probLow, probMedium, probHigh, icon: Icon, accent }) {
  return (
    <div className={`risk-section risk-section-${accent}`}>
      <div className="risk-section-header">
        <Icon size={16} />
        <span className="risk-section-label">{label}</span>
      </div>
      <div className="risk-section-body">
        <div className={`risk-pill ${getRiskClass(risk)}`}>{risk || '—'}</div>
        <div className="confidence-block">
          <span className="confidence-label">Model confidence</span>
          <span className="confidence-value">{probability != null ? `${probability.toFixed(1)}%` : '—'}</span>
        </div>
      </div>
      {probLow != null && (
        <div className="prob-bars">
          {[['Low', probLow, 'risk-low'], ['Medium', probMedium, 'risk-medium'], ['High', probHigh, 'risk-high']].map(
            ([cls, val, clsName]) => (
              <div key={cls} className="prob-bar-row">
                <span className="prob-bar-label">{cls}</span>
                <div className="prob-bar-track">
                  <div className={`prob-bar-fill ${clsName}`} style={{ width: `${val}%` }} />
                </div>
                <span className="prob-bar-pct">{val?.toFixed(1)}%</span>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}

function EnvRow({ icon: Icon, label, value }) {
  return (
    <div className="env-row">
      <Icon size={14} className="env-icon" />
      <span className="env-label">{label}</span>
      <span className="env-value">{value}</span>
    </div>
  );
}

/**
 * LocationCard — displays full prediction data for one location.
 * All risk values come directly from the backend; none are computed here.
 */
export default function LocationCard({ location, riskMode }) {
  if (!location) return null;

  const soilPct = location.soil_moisture != null
    ? `${(location.soil_moisture * 100).toFixed(1)}%`
    : '—';

  return (
    <div className="location-card">
      {/* Title */}
      <div className="lc-header">
        <MapPin size={18} className="lc-pin" />
        <div>
          <h2 className="lc-district">{location.district}</h2>
          <p className="lc-state">{location.state}</p>
        </div>
      </div>

      {/* Risk sections — ordered by active riskMode */}
      <div className="lc-risks">
        <RiskSection
          label="Flood Risk"
          risk={location.flood_risk}
          probability={location.flood_probability}
          probLow={location.flood_prob_low}
          probMedium={location.flood_prob_medium}
          probHigh={location.flood_prob_high}
          icon={Droplets}
          accent={riskMode === 'flood' ? 'primary' : 'secondary'}
        />
        <RiskSection
          label="Landslide Risk"
          risk={location.landslide_risk}
          probability={location.landslide_probability}
          probLow={location.landslide_prob_low}
          probMedium={location.landslide_prob_medium}
          probHigh={location.landslide_prob_high}
          icon={Mountain}
          accent={riskMode === 'landslide' ? 'primary' : 'secondary'}
        />
      </div>

      {/* Environmental parameters */}
      <div className="lc-env">
        <h3 className="lc-env-title">Environmental Parameters</h3>
        <div className="env-grid">
          <EnvRow icon={Droplets}     label="Rainfall"              value={`${location.rainfall?.toFixed(1)} mm/month`} />
          <EnvRow icon={Activity}     label="River Level Index"     value={`${location.river_level?.toFixed(2)} / 10`} />
          <EnvRow icon={Thermometer}  label="Soil Moisture"         value={soilPct} />
          <EnvRow icon={TrendingUp}   label="Slope"                 value={`${location.slope?.toFixed(1)}°`} />
          <EnvRow icon={Wind}         label="Elevation"             value={`${location.elevation?.toFixed(0)} m`} />
          <EnvRow icon={BarChart2}    label="Flood History"         value={location.flood_history ? 'Yes' : 'No'} />
          <EnvRow icon={BarChart2}    label="Landslide History"     value={location.landslide_history ? 'Yes' : 'No'} />
        </div>
      </div>

      {/* Confidence note */}
      <p className="confidence-note">
        Confidence represents model classification confidence on the current demo dataset,
        not real-world event probability.
      </p>
    </div>
  );
}
