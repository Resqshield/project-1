/**
 * ResQ Shield - API Service Layer
 * ================================
 * All backend communication is centralised here.
 * Components must never call fetch() directly.
 *
 * Backend: FastAPI at VITE_API_BASE_URL (default http://127.0.0.1:8000)
 * Data: Predictions come from ML-generated india_predictions.json — never
 *       calculated client-side.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8000';

/**
 * Core fetch wrapper with error handling.
 */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  try {
    const res = await fetch(url, { ...options });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body?.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new Error('Backend unavailable — is FastAPI running on port 8000?');
    }
    throw err;
  }
}

/**
 * GET /health
 * Returns status, locations count, disclaimer.
 */
export async function getHealth() {
  return apiFetch('/health');
}

/**
 * GET /api/locations
 * @param {Object} filters  e.g. { state, flood_risk, landslide_risk }
 */
export async function getLocations(filters = {}) {
  const params = new URLSearchParams();
  if (filters.state)          params.set('state', filters.state);
  if (filters.flood_risk)     params.set('flood_risk', filters.flood_risk);
  if (filters.landslide_risk) params.set('landslide_risk', filters.landslide_risk);
  const qs = params.toString();
  return apiFetch(`/api/locations${qs ? `?${qs}` : ''}`);
}

/**
 * GET /api/search?q=...
 */
export async function searchLocations(query) {
  if (!query || !query.trim()) return [];
  return apiFetch(`/api/search?q=${encodeURIComponent(query.trim())}`);
}

/**
 * GET /api/location/{district}
 * @param {string} district
 * @param {string} [state]   optional disambiguation
 */
export async function getLocation(district, state) {
  const qs = state ? `?state=${encodeURIComponent(state)}` : '';
  return apiFetch(`/api/location/${encodeURIComponent(district)}${qs}`);
}

/**
 * GET /api/states
 */
export async function getStates() {
  return apiFetch('/api/states');
}

/**
 * GET /api/summary
 */
export async function getSummary() {
  return apiFetch('/api/summary');
}

/**
 * GET /api/mountain-locations
 */
export async function getMountainLocations() {
  return apiFetch('/api/mountain-locations');
}
