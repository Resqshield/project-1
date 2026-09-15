import { MapPin, Droplets, Mountain, Globe } from 'lucide-react';

/**
 * SummaryCards — reads values from /api/summary response.
 * Numbers are NEVER hard-coded; they update automatically if predictions are regenerated.
 */
export default function SummaryCards({ summary, riskMode }) {
  if (!summary) return null;

  const cards = [
    {
      id: 'total-locations',
      label: 'Total Locations',
      value: summary.total_locations ?? '—',
      icon: MapPin,
      accent: 'neutral',
    },
    {
      id: 'flood-high',
      label: 'High Flood Risk',
      value: summary.flood?.High ?? '—',
      icon: Droplets,
      accent: riskMode === 'flood' ? 'danger' : 'muted',
    },
    {
      id: 'landslide-high',
      label: 'High Landslide Risk',
      value: summary.landslide?.High ?? '—',
      icon: Mountain,
      accent: riskMode === 'landslide' ? 'danger' : 'muted',
    },
    {
      id: 'states-covered',
      label: 'States / UTs',
      value: summary.total_states ?? '—',
      icon: Globe,
      accent: 'neutral',
    },
  ];

  return (
    <div className="summary-cards">
      {cards.map(({ id, label, value, icon: Icon, accent }) => (
        <div key={id} id={id} className={`summary-card summary-card-${accent}`}>
          <div className="summary-card-icon">
            <Icon size={18} />
          </div>
          <div className="summary-card-body">
            <span className="summary-card-value">{value}</span>
            <span className="summary-card-label">{label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
