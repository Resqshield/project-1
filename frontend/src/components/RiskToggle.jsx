import { Droplets, Mountain } from 'lucide-react';

/**
 * RiskToggle — controls which risk type the UI emphasises.
 * Does NOT recalculate any predictions. Pure UI state.
 */
export default function RiskToggle({ riskMode, onChange }) {
  return (
    <div className="risk-toggle">
      <button
        className={`toggle-btn ${riskMode === 'flood' ? 'toggle-active-flood' : ''}`}
        onClick={() => onChange('flood')}
        id="toggle-flood"
        aria-pressed={riskMode === 'flood'}
      >
        <Droplets size={16} />
        Flood Risk
      </button>
      <button
        className={`toggle-btn ${riskMode === 'landslide' ? 'toggle-active-landslide' : ''}`}
        onClick={() => onChange('landslide')}
        id="toggle-landslide"
        aria-pressed={riskMode === 'landslide'}
      >
        <Mountain size={16} />
        Landslide Risk
      </button>
    </div>
  );
}
