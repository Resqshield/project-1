from pathlib import Path
import json
import urllib.parse
import urllib.request


OUTPUT = Path(
    "data/gis/roads/osm_roads_mandi_pandoh.geojson"
)

query = """
[out:json][timeout:120];
way["highway"](31.60,76.85,31.80,77.15);
out geom;
"""

url = "https://overpass-api.de/api/interpreter"

payload = urllib.parse.urlencode(
    {"data": query}
).encode("utf-8")

request = urllib.request.Request(
    url,
    data=payload,
    headers={
        "User-Agent": "ResQShield-SIH/0.1"
    },
    method="POST",
)

print("Downloading OSM roads...")

with urllib.request.urlopen(
    request,
    timeout=180,
) as response:
    osm = json.load(response)

features = []

for element in osm.get("elements", []):
    geometry = element.get("geometry") or []

    if element.get("type") != "way":
        continue

    if len(geometry) < 2:
        continue

    coordinates = [
        [point["lon"], point["lat"]]
        for point in geometry
    ]

    tags = element.get("tags", {})

    features.append(
        {
            "type": "Feature",
            "properties": {
                "osm_id": element["id"],
                "highway": tags.get("highway"),
                "name": tags.get("name"),
                "surface": tags.get("surface"),
                "bridge": tags.get("bridge"),
                "tunnel": tags.get("tunnel"),
                "source": "OpenStreetMap / Overpass API",
                "license": "ODbL",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
        }
    )

geojson = {
    "type": "FeatureCollection",
    "name": "osm_roads_mandi_pandoh",
    "crs": {
        "type": "name",
        "properties": {
            "name": "EPSG:4326"
        },
    },
    "features": features,
}

OUTPUT.write_text(
    json.dumps(
        geojson,
        indent=2,
        ensure_ascii=False,
    ) + "\n",
    encoding="utf-8",
)

print("Created:", OUTPUT)
print("Road features:", len(features))

types = {}

for feature in features:
    road_type = feature["properties"]["highway"]
    types[road_type] = types.get(road_type, 0) + 1

print("Road types:", types)
