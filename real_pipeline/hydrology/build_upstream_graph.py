import json
import logging
from pathlib import Path
import geopandas as gpd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_upstream_graph")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HYDRO_DIR = PROJECT_ROOT / "data_real" / "hydrology" / "processed"

def build_upstream_graph():
    basins_path = HYDRO_DIR.parent / "raw" / "hybas_extracted" / "hybas_as_lev08_v1c.shp"
    if not basins_path.exists():
        log.error(f"Missing {basins_path}")
        return

    log.info("Loading HydroBASINS L8...")
    gdf = gpd.read_file(basins_path)
    
    # NEXT_DOWN maps a basin to its downstream basin
    # We want to build an upstream graph: basin -> list of immediate upstream basins
    
    upstream_adj = {}
    for idx, row in gdf.iterrows():
        hybas_id = str(row["HYBAS_ID"])
        next_down = str(row["NEXT_DOWN"])
        
        if hybas_id not in upstream_adj:
            upstream_adj[hybas_id] = []
        if next_down not in upstream_adj:
            upstream_adj[next_down] = []
            
        # hybas_id flows into next_down
        # therefore hybas_id is upstream of next_down
        if next_down != "0" and next_down != hybas_id:
            upstream_adj[next_down].append(hybas_id)
            
    # Now build full transitive closure (all upstream basins) or just return adjacency?
    # Requirement: "support upstream catchment traversal." Adjacency is enough, but full list might be better for quick lookup.
    # Let's save just the adjacency list to avoid massive files, the UI/backend can traverse it.
    
    out_path = HYDRO_DIR / "upstream_graph.json"
    with open(out_path, "w") as f:
        json.dump(upstream_adj, f)
        
    log.info(f"Built upstream graph for {len(upstream_adj)} nodes.")
    log.info(f"Saved to {out_path}")

if __name__ == "__main__":
    build_upstream_graph()
