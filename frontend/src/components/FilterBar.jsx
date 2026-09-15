/**
 * FilterBar.jsx — Phase 8
 * =======================
 * Provides state filter, risk-level filter, region quick filters,
 * high-risk button, mountain focus, and clear/reset controls.
 *
 * IMPORTANT: Filters only select which existing predictions are displayed.
 * They do NOT recalculate or change any risk value.
 */

import { Filter, X, Mountain, MapPin, Zap } from 'lucide-react';

// ── Region definitions (state names match /api/states exactly) ────────────────
export const REGION_GROUPS = {
  'All India': null,   // null = no state filter
  'Himalayan': [
    'Uttarakhand', 'Himachal Pradesh', 'Jammu & Kashmir',
    'Ladakh', 'Sikkim', 'Arunachal Pradesh',
  ],
  'North-East': [
    'Assam', 'Arunachal Pradesh', 'Meghalaya', 'Mizoram',
    'Nagaland', 'Manipur', 'Tripura', 'Sikkim',
  ],
  'South': [
    'Karnataka', 'Kerala', 'Tamil Nadu', 'Andhra Pradesh',
    'Telangana', 'Goa', 'Puducherry', 'Andaman & Nicobar',
  ],
  'West': [
    'Maharashtra', 'Gujarat', 'Rajasthan', 'Goa',
  ],
  'Central & Plains': [
    'Madhya Pradesh', 'Chhattisgarh', 'Uttar Pradesh', 'Bihar',
    'Jharkhand', 'Odisha', 'West Bengal', 'Haryana',
    'Punjab', 'Chandigarh', 'Delhi',
  ],
};

const RISK_LEVELS = ['All', 'Low', 'Medium', 'High'];

const REGION_ICONS = {
  'All India':       null,
  'Himalayan':       '🏔',
  'North-East':      '🌿',
  'South':           '🌊',
  'West':            '🏜',
  'Central & Plains':'🌾',
};

function hasActiveFilters(selectedState, riskLevel, region) {
  return selectedState !== 'All' || riskLevel !== 'All' || region !== 'All India';
}

export default function FilterBar({
  states,           // string[] from /api/states
  selectedState,    setSelectedState,
  riskLevel,        setRiskLevel,
  regionFilter,     setRegionFilter,
  riskMode,
  locations,        // full dataset for counting
  filteredCount,    // currently visible count
  onClearFilters,
  onResetMap,
}) {
  const isActive = hasActiveFilters(selectedState, riskLevel, regionFilter);

  // High risk count for active mode (across full dataset for the badge)
  const highCount = locations.filter(l =>
    (riskMode === 'flood' ? l.flood_risk : l.landslide_risk) === 'High'
  ).length;

  // High risk count in current filter
  const filteredHighCount = filteredCount; // caller already computed this
  const modeLabel = riskMode === 'flood' ? 'Flood' : 'Landslide';

  function handleStateChange(e) {
    setSelectedState(e.target.value);
    // When picking a specific state, clear region filter
    if (e.target.value !== 'All') setRegionFilter('All India');
  }

  function handleRegionChange(e) {
    setRegionFilter(e.target.value);
    // When picking a region, clear state filter
    if (e.target.value !== 'All India') setSelectedState('All');
  }

  function handleHighRiskOnly() {
    setRiskLevel(prev => prev === 'High' ? 'All' : 'High');
  }

  function handleMountainFocus() {
    setRegionFilter(prev => prev === 'Himalayan' ? 'All India' : 'Himalayan');
    setSelectedState('All');
  }

  return (
    <div className="filter-bar">
      {/* ── Row 1: Dropdowns ──────────────────────────────────── */}
      <div className="filter-row">
        <div className="filter-group">
          <label className="filter-label" htmlFor="state-filter">State</label>
          <select
            id="state-filter"
            className="filter-select"
            value={selectedState}
            onChange={handleStateChange}
            aria-label="Filter by state"
          >
            <option value="All">All States</option>
            {states.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="risk-filter">
            {modeLabel} Risk
          </label>
          <select
            id="risk-filter"
            className="filter-select"
            value={riskLevel}
            onChange={e => setRiskLevel(e.target.value)}
            aria-label={`Filter by ${modeLabel} risk level`}
          >
            {RISK_LEVELS.map(r => (
              <option key={r} value={r}>{r === 'All' ? 'All Levels' : r}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="region-filter">Region</label>
          <select
            id="region-filter"
            className="filter-select"
            value={regionFilter}
            onChange={handleRegionChange}
            aria-label="Filter by region"
          >
            {Object.keys(REGION_GROUPS).map(r => (
              <option key={r} value={r}>
                {REGION_ICONS[r] ? `${REGION_ICONS[r]} ${r}` : r}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Row 2: Quick action buttons ───────────────────────── */}
      <div className="filter-row filter-row-btns">
        <button
          className={`filter-quick-btn ${riskLevel === 'High' ? 'filter-quick-active-danger' : ''}`}
          onClick={handleHighRiskOnly}
          id="btn-high-risk-only"
          title={`Show only High ${modeLabel} locations`}
        >
          <Zap size={13} />
          High Risk Only
        </button>

        <button
          className={`filter-quick-btn ${regionFilter === 'Himalayan' ? 'filter-quick-active-mountain' : ''}`}
          onClick={handleMountainFocus}
          id="btn-mountain-focus"
          title="Focus on Himalayan / Mountain locations"
        >
          <Mountain size={13} />
          Himalayan
        </button>

        <button
          className="filter-quick-btn filter-quick-reset"
          onClick={onResetMap}
          id="btn-reset-map"
          title="Reset map to India view and clear all filters"
        >
          <MapPin size={13} />
          Reset Map
        </button>

        {isActive && (
          <button
            className="filter-clear-btn"
            onClick={onClearFilters}
            id="btn-clear-filters"
            aria-label="Clear all filters"
          >
            <X size={12} />
            Clear Filters
          </button>
        )}
      </div>

      {/* ── Active filter summary ──────────────────────────────── */}
      {isActive && (
        <div className="filter-active-bar">
          <Filter size={11} />
          <span className="filter-active-label">Active filters:</span>
          {selectedState !== 'All' && (
            <span className="filter-chip">
              {selectedState}
              <button onClick={() => setSelectedState('All')} aria-label={`Remove ${selectedState} filter`}>
                <X size={10} />
              </button>
            </span>
          )}
          {riskLevel !== 'All' && (
            <span className="filter-chip filter-chip-risk">
              {modeLabel} {riskLevel}
              <button onClick={() => setRiskLevel('All')} aria-label={`Remove ${riskLevel} filter`}>
                <X size={10} />
              </button>
            </span>
          )}
          {regionFilter !== 'All India' && (
            <span className="filter-chip">
              {regionFilter}
              <button onClick={() => setRegionFilter('All India')} aria-label={`Remove ${regionFilter} filter`}>
                <X size={10} />
              </button>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
