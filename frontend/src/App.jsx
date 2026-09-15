/**
 * App.jsx — Phase 8
 * ==================
 * Added: state filter, risk-level filter, region filter, fitRequest, clear/reset,
 *        search-clears-filters behavior, out-of-filter location note.
 *
 * IMPORTANT: No ML logic. All risk values come from FastAPI. Filters only
 * select which existing predictions are visible — never change risk labels.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Header        from './components/Header';
import RiskToggle    from './components/RiskToggle';
import SearchBar     from './components/SearchBar';
import SummaryCards  from './components/SummaryCards';
import LocationCard  from './components/LocationCard';
import FilterBar, { REGION_GROUPS } from './components/FilterBar';
import RiskMap       from './components/RiskMap';
import { LoadingSpinner, ErrorState } from './components/LoadingState';
import { getHealth, getLocations, getSummary, getLocation, getStates } from './services/api';
import { AlertTriangle } from 'lucide-react';

const DEFAULT_DISTRICT = 'Dehradun';
const DEFAULT_STATE    = 'Uttarakhand';

export default function App() {
  // ── Core data state ─────────────────────────────────────────────────────────
  const [locations,     setLocations]     = useState([]);
  const [summary,       setSummary]       = useState(null);
  const [states,        setStates]        = useState([]);
  const [selectedLoc,   setSelectedLoc]   = useState(null);
  const [backendStatus, setBackendStatus] = useState('unknown');

  // ── UI/filter state ──────────────────────────────────────────────────────────
  const [riskMode,       setRiskMode]       = useState('flood');
  const [selectedState,  setSelectedState]  = useState('All');
  const [riskLevel,      setRiskLevel]      = useState('All');
  const [regionFilter,   setRegionFilter]   = useState('All India');

  // ── Loading / error state ────────────────────────────────────────────────────
  const [appLoading,  setAppLoading]  = useState(true);
  const [appError,    setAppError]    = useState(null);
  const [locLoading,  setLocLoading]  = useState(false);
  const [locError,    setLocError]    = useState(null);

  // ── fitRequest: increment to trigger map fitBounds ───────────────────────────
  const [fitRequest, setFitRequest] = useState(0);

  // ── Initial data load ────────────────────────────────────────────────────────
  const loadInitialData = useCallback(async () => {
    setAppLoading(true);
    setAppError(null);
    try {
      await getHealth();
      setBackendStatus('connected');

      const [summaryData, locsData, statesData] = await Promise.all([
        getSummary(),
        getLocations(),
        getStates(),
      ]);
      setSummary(summaryData);
      setLocations(locsData);
      setStates(statesData);

      // Load default location
      try {
        const def = await getLocation(DEFAULT_DISTRICT, DEFAULT_STATE);
        setSelectedLoc(def);
      } catch {
        if (locsData.length > 0) {
          const first = await getLocation(locsData[0].district, locsData[0].state);
          setSelectedLoc(first);
        }
      }
    } catch (err) {
      setBackendStatus('error');
      setAppError(err.message || 'Failed to connect to backend.');
    } finally {
      setAppLoading(false);
    }
  }, []);

  useEffect(() => { loadInitialData(); }, [loadInitialData]);

  // ── Filter pipeline (useMemo — never mutates locations) ─────────────────────
  const filteredLocations = useMemo(() => {
    let result = locations;

    // 1. Region filter (uses REGION_GROUPS state sets)
    if (regionFilter !== 'All India') {
      const regionStates = REGION_GROUPS[regionFilter];
      if (regionStates) {
        result = result.filter(l => regionStates.includes(l.state));
      }
    }

    // 2. State filter (overrides region if specific state chosen)
    if (selectedState !== 'All') {
      result = result.filter(l => l.state === selectedState);
    }

    // 3. Risk-level filter — uses active riskMode
    if (riskLevel !== 'All') {
      result = result.filter(l =>
        (riskMode === 'flood' ? l.flood_risk : l.landslide_risk) === riskLevel
      );
    }

    return result;
  }, [locations, selectedState, riskLevel, regionFilter, riskMode]);

  // ── Trigger fitBounds when geographic filters change ─────────────────────────
  const prevGeoFilter = useRef({ selectedState, regionFilter });
  useEffect(() => {
    const prev = prevGeoFilter.current;
    if (prev.selectedState !== selectedState || prev.regionFilter !== regionFilter) {
      prevGeoFilter.current = { selectedState, regionFilter };
      setFitRequest(n => n + 1);
    }
  }, [selectedState, regionFilter]);

  // ── Is selected location visible under current filters? ─────────────────────
  const selectedLocHidden = useMemo(() => {
    if (!selectedLoc || filteredLocations.length === locations.length) return false;
    return !filteredLocations.some(
      l => l.district.toLowerCase() === selectedLoc.district?.toLowerCase() &&
           l.state.toLowerCase()    === selectedLoc.state?.toLowerCase()
    );
  }, [selectedLoc, filteredLocations, locations.length]);

  // ── Select a location (from search or marker click) ──────────────────────────
  const handleSelectLocation = useCallback(async (district, state) => {
    setLocLoading(true);
    setLocError(null);

    // Search always clears geographic filters so selected location is visible
    setSelectedState('All');
    setRegionFilter('All India');
    // Keep riskLevel — user may want to keep High risk filter

    try {
      const data = await getLocation(district, state);
      setSelectedLoc(data);
    } catch (err) {
      setLocError(`Could not load ${district}: ${err.message}`);
    } finally {
      setLocLoading(false);
    }
  }, []);

  // ── Clear filters ─────────────────────────────────────────────────────────────
  const handleClearFilters = useCallback(() => {
    setSelectedState('All');
    setRiskLevel('All');
    setRegionFilter('All India');
  }, []);

  // ── Reset map (clear filters + return to India view) ──────────────────────────
  const handleResetMap = useCallback(() => {
    setSelectedState('All');
    setRiskLevel('All');
    setRegionFilter('All India');
    setSelectedLoc(null);                // release flyTo lock
    setFitRequest(n => n + 1);          // trigger fitBounds with full dataset → India view
  }, []);

  // ── High count for active mode (for display in FilterBar) ────────────────────
  const filteredHighCount = useMemo(() =>
    filteredLocations.filter(l =>
      (riskMode === 'flood' ? l.flood_risk : l.landslide_risk) === 'High'
    ).length,
  [filteredLocations, riskMode]);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      <Header backendStatus={backendStatus} />

      <div className="app-body">
        {/* ── Sidebar ──────────────────────────────────────────────────────── */}
        <aside className="sidebar">
          <div className="sidebar-controls">
            <RiskToggle riskMode={riskMode} onChange={setRiskMode} />
            <SearchBar onSelect={handleSelectLocation} riskMode={riskMode} />
          </div>

          {/* Filter bar */}
          {!appLoading && !appError && (
            <FilterBar
              states={states}
              selectedState={selectedState}   setSelectedState={setSelectedState}
              riskLevel={riskLevel}           setRiskLevel={setRiskLevel}
              regionFilter={regionFilter}     setRegionFilter={setRegionFilter}
              riskMode={riskMode}
              locations={locations}
              filteredCount={filteredHighCount}
              onClearFilters={handleClearFilters}
              onResetMap={handleResetMap}
            />
          )}

          <SummaryCards summary={summary} riskMode={riskMode} />

          {/* Location panel */}
          <div className="location-panel">
            {locLoading && <LoadingSpinner message="Loading location…" />}
            {locError   && <ErrorState message={locError} />}
            {!locLoading && !locError && (
              <>
                {selectedLocHidden && (
                  <div className="loc-hidden-notice" role="alert">
                    <AlertTriangle size={13} />
                    <span>
                      {selectedLoc?.district} is outside current filters.
                      Showing full details below.
                    </span>
                  </div>
                )}
                <LocationCard location={selectedLoc} riskMode={riskMode} />
              </>
            )}
          </div>
        </aside>

        {/* ── Main content area ─────────────────────────────────────────── */}
        <main className="main-content">
          {appLoading ? (
            <div className="map-placeholder">
              <LoadingSpinner message="Connecting to backend…" />
            </div>
          ) : appError ? (
            <div className="map-placeholder">
              <ErrorState message={appError} onRetry={loadInitialData} />
            </div>
          ) : (
            <RiskMap
              locations={filteredLocations}
              totalCount={locations.length}
              selectedLocation={selectedLocHidden ? null : selectedLoc}
              riskMode={riskMode}
              onLocationSelect={handleSelectLocation}
              fitRequest={fitRequest}
              onClearFilters={handleClearFilters}
            />
          )}
        </main>
      </div>

      <footer className="disclaimer-footer">
        <span>
          ⚠️ Synthetic/demo predictions only. ResQ Shield is not currently an operational disaster warning system.
        </span>
      </footer>
    </div>
  );
}
