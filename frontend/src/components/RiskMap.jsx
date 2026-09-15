/**
 * RiskMap.jsx — Phase 7 + Phase 8
 * =================================
 * Interactive India Risk Map using React-Leaflet + OpenStreetMap.
 * CircleMarkers colored by riskMode (flood | landslide) from API data only.
 *
 * Phase 8 additions:
 *  - filteredLocations vs totalCount for Visible/Total header
 *  - fitBounds when filter changes (via fitRequest prop)
 *  - empty-filter overlay
 *  - improved tooltip shows active risk level
 *
 * Props:
 *   locations         — filtered array to render (from App filteredLocations)
 *   totalCount        — total locations loaded (dynamic from API)
 *   selectedLocation  — current selected location object (or null)
 *   riskMode          — 'flood' | 'landslide'
 *   onLocationSelect(district, state) — callback when marker/popup clicked
 *   fitRequest        — incrementing number; triggers fitBounds when changed
 */

import { useEffect, useRef, useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  Tooltip,
  useMap,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// ── Constants ─────────────────────────────────────────────────────────────────
const INDIA_CENTER  = [22.5, 80];
const INDIA_ZOOM    = 5;
const FLY_ZOOM      = 9;
const FLY_DURATION  = 1.2;

const INDIA_MAX_BOUNDS = [
  [6.0,  67.0],
  [38.0, 98.0],
];

// ── Risk colour map (centralised, exported for use in FilterBar/Legend) ───────
export const RISK_COLORS = {
  High:   '#ef4444',
  Medium: '#f59e0b',
  Low:    '#22c55e',
};

export function getRiskColor(riskValue) {
  return RISK_COLORS[riskValue] || '#94a3b8';
}

function getRisk(location, riskMode) {
  return riskMode === 'flood' ? location.flood_risk : location.landslide_risk;
}

function getConfidence(location, riskMode) {
  return riskMode === 'flood'
    ? location.flood_probability
    : location.landslide_probability;
}

// ── MapController — flyTo on selection, fitBounds on filter change ────────────
function MapController({ selectedLocation, locations, fitRequest }) {
  const map           = useMap();
  const prevLocKey    = useRef(null);
  const prevFitReq    = useRef(fitRequest);

  // flyTo selected location (takes priority)
  useEffect(() => {
    if (!selectedLocation) return;
    const key = `${selectedLocation.district}|${selectedLocation.state}`;
    if (key === prevLocKey.current) return;
    prevLocKey.current = key;
    const { latitude, longitude } = selectedLocation;
    if (!isFinite(latitude) || !isFinite(longitude)) return;
    map.flyTo([latitude, longitude], FLY_ZOOM, { duration: FLY_DURATION });
  }, [selectedLocation, map]);

  // fitBounds when filter changes (fitRequest increments)
  useEffect(() => {
    if (fitRequest === prevFitReq.current) return;
    prevFitReq.current = fitRequest;
    if (!locations || locations.length === 0) return;

    const valid = locations.filter(l => isFinite(l.latitude) && isFinite(l.longitude));
    if (valid.length === 0) return;

    if (valid.length === 1) {
      map.flyTo([valid[0].latitude, valid[0].longitude], FLY_ZOOM, { duration: 0.8 });
      return;
    }

    const lats = valid.map(l => l.latitude);
    const lons = valid.map(l => l.longitude);
    const bounds = [
      [Math.min(...lats) - 0.5, Math.min(...lons) - 0.5],
      [Math.max(...lats) + 0.5, Math.max(...lons) + 0.5],
    ];
    map.flyToBounds(bounds, { padding: [30, 30], duration: 0.9, maxZoom: 13 });
  }, [fitRequest, locations, map]);

  return null;
}

// ── Legend overlay ────────────────────────────────────────────────────────────
function MapLegend({ riskMode, locations }) {
  const counts = { High: 0, Medium: 0, Low: 0 };
  locations.forEach(l => {
    const r = riskMode === 'flood' ? l.flood_risk : l.landslide_risk;
    if (r in counts) counts[r]++;
  });

  return (
    <div className="map-legend" role="complementary" aria-label="Risk level legend">
      <div className="legend-title">
        {riskMode === 'flood' ? 'Flood Risk' : 'Landslide Risk'}
      </div>
      {[['High', RISK_COLORS.High], ['Medium', RISK_COLORS.Medium], ['Low', RISK_COLORS.Low]].map(
        ([label, color]) => (
          <div key={label} className="legend-row">
            <span className="legend-dot" style={{ background: color }} aria-hidden="true" />
            <span className="legend-label">{label}</span>
            <span className="legend-count">{counts[label]}</span>
          </div>
        )
      )}
      <div className="legend-total">{locations.length} shown</div>
    </div>
  );
}

// ── Map overlay header ────────────────────────────────────────────────────────
function MapOverlayHeader({ riskMode, visibleCount, totalCount }) {
  const modeLabel = riskMode === 'flood' ? 'Flood Risk' : 'Landslide Risk';
  const isFiltered = visibleCount < totalCount;
  return (
    <div className="map-overlay-header">
      <span className="map-overlay-title">India {modeLabel} Map</span>
      <span className={`map-overlay-count ${isFiltered ? 'map-count-filtered' : ''}`}>
        {isFiltered
          ? `Visible: ${visibleCount} / ${totalCount}`
          : `${totalCount} locations`}
      </span>
    </div>
  );
}

// ── Empty filter overlay ──────────────────────────────────────────────────────
function EmptyFilterOverlay({ onClearFilters }) {
  return (
    <div className="map-empty-overlay">
      <span className="map-empty-icon">🔍</span>
      <p className="map-empty-msg">No locations match the current filters.</p>
      {onClearFilters && (
        <button className="map-empty-clear" onClick={onClearFilters} id="map-clear-filters-btn">
          Clear Filters
        </button>
      )}
    </div>
  );
}

// ── Individual CircleMarker ───────────────────────────────────────────────────
function RiskMarker({ location, riskMode, isSelected, onSelect }) {
  const risk       = getRisk(location, riskMode);
  const confidence = getConfidence(location, riskMode);
  const color      = getRiskColor(risk);

  const baseRadius  = risk === 'High' ? 8 : risk === 'Medium' ? 7 : 6;
  const radius      = isSelected ? baseRadius + 4 : baseRadius;

  const pathOptions = {
    radius,
    color:       isSelected ? '#ffffff' : 'rgba(0,0,0,0.45)',
    weight:      isSelected ? 3 : 1.5,
    fillColor:   color,
    fillOpacity: isSelected ? 0.95 : 0.80,
  };

  const handleClick = useCallback(() => {
    onSelect(location.district, location.state);
  }, [location, onSelect]);

  const activeRisk  = riskMode === 'flood' ? 'Flood' : 'Landslide';
  const otherRisk   = riskMode === 'flood' ? 'Landslide' : 'Flood';
  const otherValue  = riskMode === 'flood' ? location.landslide_risk : location.flood_risk;
  const otherConf   = riskMode === 'flood' ? location.landslide_probability : location.flood_probability;

  return (
    <CircleMarker
      center={[location.latitude, location.longitude]}
      pathOptions={pathOptions}
      eventHandlers={{ click: handleClick }}
    >
      {/* Hover tooltip — district + active risk */}
      <Tooltip direction="top" offset={[0, -(radius + 2)]} opacity={0.93}>
        <span className="marker-tooltip">
          {location.district}, {location.state}
          <br />
          <span style={{ color, fontWeight: 600 }}>
            {activeRisk}: {risk}
          </span>
          {confidence != null && (
            <span style={{ color: '#8b949e' }}> · {confidence.toFixed(1)}%</span>
          )}
        </span>
      </Tooltip>

      {/* Click popup */}
      <Popup>
        <div className="marker-popup">
          <div className="popup-header">
            <strong>{location.district}</strong>
            <span className="popup-state">{location.state}</span>
          </div>
          <div className="popup-risks">
            <div className={`popup-risk-row ${riskMode === 'flood' ? 'popup-primary' : ''}`}>
              <span className="popup-risk-label">Flood</span>
              <span className="popup-risk-value" style={{ color: getRiskColor(location.flood_risk) }}>
                {location.flood_risk}
              </span>
              <span className="popup-confidence">{location.flood_probability?.toFixed(1)}%</span>
            </div>
            <div className={`popup-risk-row ${riskMode === 'landslide' ? 'popup-primary' : ''}`}>
              <span className="popup-risk-label">Landslide</span>
              <span className="popup-risk-value" style={{ color: getRiskColor(location.landslide_risk) }}>
                {location.landslide_risk}
              </span>
              <span className="popup-confidence">{location.landslide_probability?.toFixed(1)}%</span>
            </div>
          </div>
          <div className="popup-env">
            <span>{location.rainfall?.toFixed(0)} mm/mo</span>
            <span>·</span>
            <span>Slope {location.slope?.toFixed(1)}°</span>
            <span>·</span>
            <span>{location.elevation?.toFixed(0)} m</span>
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
}

// ── Main RiskMap ──────────────────────────────────────────────────────────────
export default function RiskMap({
  locations,          // filtered locations to display
  totalCount,         // full dataset count (dynamic from /api/locations)
  selectedLocation,
  riskMode,
  onLocationSelect,
  fitRequest,         // increments to trigger fitBounds
  onClearFilters,
}) {
  const validLocations = (locations || []).filter(
    l => isFinite(l.latitude) && isFinite(l.longitude)
  );

  return (
    <div className="risk-map-wrapper">
      <MapOverlayHeader
        riskMode={riskMode}
        visibleCount={validLocations.length}
        totalCount={totalCount || validLocations.length}
      />

      <div className="map-container-relative">
        <MapContainer
          center={INDIA_CENTER}
          zoom={INDIA_ZOOM}
          className="leaflet-map"
          maxBounds={INDIA_MAX_BOUNDS}
          maxBoundsViscosity={0.6}
          minZoom={4}
          maxZoom={16}
          scrollWheelZoom={true}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
          />

          <MapController
            selectedLocation={selectedLocation}
            locations={validLocations}
            fitRequest={fitRequest}
          />

          {validLocations.map((loc) => {
            const isSelected =
              selectedLocation &&
              loc.district.toLowerCase() === selectedLocation.district?.toLowerCase() &&
              loc.state.toLowerCase()    === selectedLocation.state?.toLowerCase();

            return (
              <RiskMarker
                key={`${loc.district}-${loc.state}`}
                location={loc}
                riskMode={riskMode}
                isSelected={!!isSelected}
                onSelect={onLocationSelect}
              />
            );
          })}
        </MapContainer>

        {/* Empty filter overlay — rendered on top of map */}
        {validLocations.length === 0 && (
          <EmptyFilterOverlay onClearFilters={onClearFilters} />
        )}

        {/* Legend — always shown */}
        <MapLegend riskMode={riskMode} locations={validLocations} />
      </div>
    </div>
  );
}
