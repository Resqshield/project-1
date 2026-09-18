/**
 * frontend/src/realmap/AdminSearchBar.jsx
 * =========================================
 * Search bar for admin hierarchy disambiguation.
 * Calls GET /api/real/search?q=... and shows results
 * with full parent path to disambiguate duplicate names.
 */

import { useState, useCallback, useRef, useEffect } from "react";

export default function AdminSearchBar({ onSelect }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef(null);
  const containerRef = useRef(null);

  const search = useCallback(async (q) => {
    if (!q || q.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      console.log(`[Search Diagnostics] Requesting search for: "${q}"`);
      const resp = await fetch(
        `/api/real/search?q=${encodeURIComponent(q)}&limit=10`
      );
      if (!resp.ok) throw new Error("Search failed");
      const data = await resp.json();
      console.log(`[Search Diagnostics] Response received:`, data);
      setResults(data.results ?? []);
      setOpen(true);
    } catch (e) {
      console.warn("Admin search error:", e);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (e) => {
    const q = e.target.value;
    setQuery(q);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(q), 250);
  };

  const handleSelect = (result) => {
    setQuery(result.name);
    setOpen(false);
    onSelect(result);
  };

  const handleClear = () => {
    setQuery("");
    setResults([]);
    setOpen(false);
  };

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const typeIcon = (type) => {
    if (type === "state") return "🗺";
    if (type === "district") return "📍";
    if (type === "subdistrict") return "🔵";
    return "📌";
  };

  return (
    <div className="admin-search" ref={containerRef}>
      <div className="search-input-row">
        <svg className="search-icon" width="14" height="14" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          type="text"
          className="search-input"
          placeholder="Search state, district…"
          value={query}
          onChange={handleChange}
          onFocus={() => results.length > 0 && setOpen(true)}
        />
        {loading && <div className="search-spinner" />}
        {query && !loading && (
          <button className="search-clear" onClick={handleClear} title="Clear">×</button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="search-dropdown">
          {results.map((r, i) => (
            <button
              key={`${r.code}-${i}`}
              className="search-result"
              onClick={() => handleSelect(r)}
            >
              <span className="result-icon">{typeIcon(r.type)}</span>
              <div className="result-body">
                <div className="result-name">{r.name}</div>
                <div className="result-path">{r.parent_path}</div>
              </div>
              <span className="result-type">{r.type}</span>
            </button>
          ))}
        </div>
      )}

      {open && results.length === 0 && !loading && query.length >= 2 && (
        <div className="search-dropdown">
          <div className="search-no-results">No results for "{query}"</div>
        </div>
      )}

      <style>{`
        .admin-search { padding: 10px 12px; border-bottom: 1px solid rgba(51,65,85,0.4); position: relative; }
        .search-input-row { display: flex; align-items: center; gap: 6px; background: rgba(30,41,59,0.8); border: 1px solid rgba(51,65,85,0.6); border-radius: 6px; padding: 6px 10px; }
        .search-icon { color: #475569; flex-shrink: 0; }
        .search-input { flex: 1; background: none; border: none; outline: none; color: #e2e8f0; font-size: 12px; min-width: 0; }
        .search-input::placeholder { color: #475569; }
        .search-spinner { width: 12px; height: 12px; border: 1.5px solid rgba(59,130,246,0.3); border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0; }
        .search-clear { background: none; border: none; color: #475569; cursor: pointer; font-size: 14px; padding: 0 2px; line-height: 1; }
        .search-clear:hover { color: #94a3b8; }
        .search-dropdown { position: absolute; top: calc(100% - 8px); left: 12px; right: 12px; background: rgba(15,23,42,0.97); border: 1px solid rgba(51,65,85,0.6); border-radius: 8px; z-index: 100; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
        .search-result { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; background: none; border: none; cursor: pointer; text-align: left; transition: background 0.15s; border-bottom: 1px solid rgba(51,65,85,0.3); }
        .search-result:last-child { border-bottom: none; }
        .search-result:hover { background: rgba(59,130,246,0.1); }
        .result-icon { font-size: 12px; flex-shrink: 0; }
        .result-body { flex: 1; min-width: 0; }
        .result-name { font-size: 12px; color: #e2e8f0; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .result-path { font-size: 10px; color: #475569; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 1px; }
        .result-type { font-size: 9px; color: #475569; background: rgba(51,65,85,0.5); border-radius: 3px; padding: 1px 4px; flex-shrink: 0; }
        .search-no-results { padding: 12px 16px; font-size: 12px; color: #475569; text-align: center; }
      `}</style>
    </div>
  );
}
