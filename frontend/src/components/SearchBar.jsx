import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, MapPin } from 'lucide-react';
import { searchLocations } from '../services/api';

const DEBOUNCE_MS = 300;

function getRiskClass(risk) {
  if (!risk) return '';
  const r = risk.toLowerCase();
  if (r === 'high')   return 'risk-high';
  if (r === 'medium') return 'risk-medium';
  return 'risk-low';
}

/**
 * SearchBar with debounced backend search and dropdown suggestions.
 * Uses GET /api/search?q=... — no client-side filtering.
 */
export default function SearchBar({ onSelect, riskMode }) {
  const [query, setQuery]       = useState('');
  const [results, setResults]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [open, setOpen]         = useState(false);
  const [error, setError]       = useState(null);
  const debounceRef             = useRef(null);
  const wrapperRef              = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const doSearch = useCallback(async (q) => {
    const trimmed = q.trim();
    if (!trimmed) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await searchLocations(trimmed);
      setResults(data);
      setOpen(true);
    } catch (err) {
      setError(err.message);
      setResults([]);
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }, []);

  function handleChange(e) {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(debounceRef.current);
    if (!val.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => doSearch(val), DEBOUNCE_MS);
  }

  function handleClear() {
    setQuery('');
    setResults([]);
    setOpen(false);
  }

  function handleSelect(loc) {
    setQuery(`${loc.district}, ${loc.state}`);
    setOpen(false);
    onSelect(loc.district, loc.state);
  }

  const primaryRisk = riskMode === 'flood' ? 'flood_risk' : 'landslide_risk';

  return (
    <div className="searchbar-wrapper" ref={wrapperRef}>
      <div className="searchbar-input-row">
        <Search size={16} className="searchbar-icon" />
        <input
          id="location-search"
          className="searchbar-input"
          type="text"
          placeholder="Search district or state…"
          value={query}
          onChange={handleChange}
          onFocus={() => results.length > 0 && setOpen(true)}
          autoComplete="off"
          aria-label="Search locations"
          aria-autocomplete="list"
          aria-expanded={open}
        />
        {query && (
          <button className="searchbar-clear" onClick={handleClear} aria-label="Clear search">
            <X size={14} />
          </button>
        )}
        {loading && <span className="searchbar-spinner" />}
      </div>

      {open && (
        <ul className="search-dropdown" role="listbox" id="search-results">
          {error ? (
            <li className="dropdown-msg dropdown-error">{error}</li>
          ) : results.length === 0 ? (
            <li className="dropdown-msg">No matching locations found</li>
          ) : (
            results.slice(0, 10).map((loc) => (
              <li
                key={`${loc.district}-${loc.state}`}
                className="dropdown-item"
                role="option"
                onMouseDown={() => handleSelect(loc)}
              >
                <MapPin size={13} className="dropdown-pin" />
                <div className="dropdown-text">
                  <span className="dropdown-district">{loc.district}</span>
                  <span className="dropdown-state">{loc.state}</span>
                </div>
                <div className="dropdown-risks">
                  <span className={`risk-badge ${getRiskClass(loc.flood_risk)}`}>
                    F: {loc.flood_risk}
                  </span>
                  <span className={`risk-badge ${getRiskClass(loc.landslide_risk)}`}>
                    L: {loc.landslide_risk}
                  </span>
                </div>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
