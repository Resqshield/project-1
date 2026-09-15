# -*- coding: utf-8 -*-
"""
real_pipeline/admin/search_admin.py
=====================================
Local admin hierarchy search prototype.

Features:
  - Full-text search across village_name, district_name, subdistrict_name, state_name.
  - Returns: entity type, parents, official LGD code, lat/lon (if available).
  - Disambiguates duplicates: "Chamoli" as district vs. other entity.
  - Never uses village name alone as primary key — always returns LGD code.
  - Works fully offline from admin_locations.parquet.

API prototype (FastAPI):
  GET /admin/search?q=Raini
  GET /admin/search?q=Chamoli&type=district
  GET /admin/entity/<village_code>

Usage:
    # CLI search:
    python real_pipeline/admin/search_admin.py --query "Raini"
    python real_pipeline/admin/search_admin.py --query "Chamoli" --type district

    # Run as API server:
    python real_pipeline/admin/search_admin.py --serve --port 8001
"""

import sys
import json
import logging
import argparse
import unicodedata
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROC_DIR     = PROJECT_ROOT / "data_real" / "admin" / "processed"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("admin_search")

# ── Global in-memory index ─────────────────────────────────────────────────────
_df: Optional[pd.DataFrame] = None
_index: Dict[str, List[int]] = {}  # normalized_token → list of row indices


def normalize(text: str) -> str:
    """Normalize text for search."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def build_index(df: pd.DataFrame):
    """Build inverted index over all name columns."""
    global _index, _df
    _df = df
    _index = {}
    name_cols = [
        c for c in ["village_name", "gp_name", "block_name",
                     "subdistrict_name", "district_name", "state_name"]
        if c in df.columns
    ]
    log.info(f"Building search index over columns: {name_cols}")
    for idx, row in df.iterrows():
        for col in name_cols:
            val = row.get(col)
            if not val or not isinstance(val, str):
                continue
            norm_val = normalize(val)
            if norm_val not in _index:
                _index[norm_val] = []
            _index[norm_val].append(idx)
    log.info(f"Index built: {len(_index):,} unique normalized tokens across {len(df):,} rows")


def search(query: str, entity_type: Optional[str] = None,
           max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Search the admin index.
    entity_type: one of 'village', 'gp', 'block', 'subdistrict', 'district', 'state'
    Returns list of result dicts.
    """
    if _df is None:
        raise RuntimeError("Index not built. Call build_index() first.")

    norm_query = normalize(query)
    if not norm_query:
        return []

    # Collect matching row indices (exact + prefix)
    matched_indices = set()
    for token, indices in _index.items():
        if norm_query in token:
            matched_indices.update(indices)

    if not matched_indices:
        return []

    rows = _df.iloc[list(matched_indices)]

    # Determine match entity type per row
    results = []
    seen_village_codes = set()  # deduplicate same village code

    for _, row in rows.iterrows():
        row_results = []

        # Check which name column triggered the match
        name_cols_ordered = [
            ("village",     "village_name",     "village_code"),
            ("gp",          "gp_name",          "gp_code"),
            ("block",       "block_name",       "block_code"),
            ("subdistrict", "subdistrict_name", "subdistrict_code"),
            ("district",    "district_name",    "district_code"),
            ("state",       "state_name",       "state_code"),
        ]

        for etype, name_col, code_col in name_cols_ordered:
            if name_col not in row.index:
                continue
            name = row.get(name_col)
            if not name or not isinstance(name, str):
                continue
            if norm_query not in normalize(name):
                continue
            if entity_type and etype != entity_type:
                continue

            # Build parent hierarchy
            parents = {}
            if etype not in ("state",):
                for ptype, pcol, _ in reversed(name_cols_ordered):
                    if ptype == etype:
                        break
                    pname = row.get(f"{ptype}_name") if f"{ptype}_name" in row.index else None
                    pcode = row.get(f"{ptype}_code") if f"{ptype}_code" in row.index else None
                    if pname and not pd.isna(pname):
                        parents[ptype] = {"name": str(pname), "code": _safe_int(pcode)}

            code = row.get(code_col)
            dedup_key = f"{etype}:{_safe_int(code)}"

            result = {
                "entity_type":    etype,
                "name":           str(name),
                "official_code":  _safe_int(code),
                "parents":        parents,
                "lat":            _safe_float(row.get("latitude")),
                "lon":            _safe_float(row.get("longitude")),
                "geometry_available": bool(row.get("geometry_available", False)),
                "admin_source":   row.get("admin_source", None),
                "village_status": row.get("village_status", None) if etype == "village" else None,
                "_dedup_key":     dedup_key,
            }
            row_results.append(result)

        for r in row_results:
            dk = r.pop("_dedup_key")
            if dk not in seen_village_codes:
                seen_village_codes.add(dk)
                results.append(r)

    # Sort: exact matches first, then partial
    results.sort(key=lambda r: (
        0 if normalize(r["name"]) == norm_query else 1,
        r["entity_type"],
        r["name"],
    ))

    return results[:max_results]


def _safe_int(val) -> Optional[int]:
    try:
        v = int(float(val))
        return v
    except (TypeError, ValueError):
        return None


def _safe_float(val) -> Optional[float]:
    try:
        v = float(val)
        return v if not pd.isna(v) else None
    except (TypeError, ValueError):
        return None


def load_data() -> pd.DataFrame:
    """Load admin_locations from parquet or CSV."""
    candidates = [
        PROC_DIR / "admin_locations.parquet",
        PROC_DIR / "admin_locations.csv",
    ]
    for path in candidates:
        if path.exists():
            log.info(f"Loading: {path}")
            if path.suffix == ".parquet":
                return pd.read_parquet(path)
            else:
                return pd.read_csv(path, dtype=str, low_memory=False)
    return None


def print_results(results: List[dict], query: str):
    """Pretty-print search results."""
    if not results:
        print(f"\nNo results for: '{query}'")
        return

    print(f"\n=== Search: '{query}' — {len(results)} result(s) ===\n")
    for i, r in enumerate(results, 1):
        parents_str = " → ".join(
            f"{k.title()}: {v['name']} (code:{v['code']})"
            for k, v in r["parents"].items()
        ) if r["parents"] else "(top level)"

        coord_str = (
            f"({r['lat']:.4f}°N, {r['lon']:.4f}°E)"
            if r["lat"] and r["lon"] else "No coordinates"
        )
        print(f"[{i}] {r['entity_type'].upper()}: {r['name']}")
        print(f"     Official LGD Code : {r['official_code']}")
        print(f"     Parents           : {parents_str}")
        print(f"     Coordinates       : {coord_str}")
        if r.get("village_status"):
            print(f"     Status            : {r['village_status']}")
        print()


# ── FastAPI micro-server ───────────────────────────────────────────────────────
def run_server(port: int):
    """Run as a lightweight FastAPI search server on port 8001 (separate from main API)."""
    try:
        from fastapi import FastAPI, Query as FQuery
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
    except ImportError:
        log.error("fastapi/uvicorn not installed. Run: pip install fastapi uvicorn")
        sys.exit(1)

    api = FastAPI(
        title="ResQ Shield Admin Search API",
        description="Hierarchy search over real LGD admin data. No synthetic data.",
        version="0.1.0-real",
    )
    api.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

    @api.get("/admin/search")
    def api_search(
        q: str = FQuery(..., min_length=1, description="Search query"),
        type: Optional[str] = FQuery(None, description="entity type filter: village|district|state|…"),
        limit: int = FQuery(20, ge=1, le=100),
    ):
        results = search(q, entity_type=type, max_results=limit)
        return {"query": q, "count": len(results), "results": results}

    @api.get("/admin/entity/{village_code}")
    def api_entity(village_code: int):
        if _df is None:
            return {"error": "Index not loaded"}
        matches = _df[_df["village_code"] == village_code]
        if len(matches) == 0:
            return {"error": f"village_code {village_code} not found"}
        row = matches.iloc[0]
        return row.where(pd.notnull(row), other=None).to_dict()

    @api.get("/admin/health")
    def api_health():
        return {
            "status": "ok",
            "data_type": "REAL_OFFICIAL — NOT SYNTHETIC",
            "rows_indexed": len(_df) if _df is not None else 0,
            "index_tokens": len(_index),
        }

    log.info(f"Starting admin search API on port {port}…")
    uvicorn.run(api, host="0.0.0.0", port=port)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Admin hierarchy search")
    parser.add_argument("--query", "-q", type=str, default=None, help="Search query")
    parser.add_argument("--type", "-t", type=str, default=None,
                        help="Entity type filter: village|gp|block|subdistrict|district|state")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--serve", action="store_true", help="Run as API server")
    parser.add_argument("--port", type=int, default=8001, help="Server port")
    args = parser.parse_args()

    df = load_data()
    if df is None:
        log.error("No admin data found. Run ingest_lgd.py first.")
        log.error(f"Expected: {PROC_DIR / 'admin_locations.parquet'}")
        sys.exit(1)

    build_index(df)

    if args.serve:
        run_server(args.port)
        return

    if args.query:
        results = search(args.query, entity_type=args.type, max_results=args.limit)
        print_results(results, args.query)
    else:
        # Interactive mode
        log.info("Admin search ready. Enter queries (Ctrl+C to exit).")
        print("\nResQ Shield Admin Search (Real LGD Data)")
        print("Type a village, district, block or state name. Ctrl+C to exit.\n")
        while True:
            try:
                q = input("Search > ").strip()
                if q:
                    results = search(q, max_results=args.limit)
                    print_results(results, q)
            except KeyboardInterrupt:
                print("\nBye.")
                break
            except EOFError:
                break


if __name__ == "__main__":
    main()
