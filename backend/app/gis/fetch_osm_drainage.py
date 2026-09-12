from pathlib import Path
import json
import urllib.parse
import urllib.request


OUTPUT = Path("data/gis/drainage/osm_waterways_mandi_pandoh.geojson")

query = """
[out:json][timeout:90];
way["waterway"](31.60,76.85,31.80,77.15);
out geom;
"""

url = "https://overpass-api.de/api/interpreter"
payload = urllib.parse.urlencode({"data": query}).encode("utf-8")

request = urllib.request.Request(
    url,
    data=payload,
    headers={
        "User-Agent": "ResQShield-SIH/0.1"
    },
    method="POST",
)

print("Downloading OSM drainage data...")

with urllib.request.urlopen(request, timeout=120) as response:
    osm = json.load(response)

features = []

for element in osm.get("elements", []):
    geometry = element.get("geometry") or []

    if element.get("type") != "way" or len(geometry) < 2:
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
                "waterway": tags.get("waterway"),
                "name": tags.get("name"),
                "source": "OpenStreetMap / Overpass API",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
        }
    )

geojson = {
    "type": "FeatureCollection",
    "name": "osm_waterways_mandi_pandoh",
    "crs": {
        "type": "name",
        "properties": {
            "name": "EPSG:4326"
        }
    },
    "features": features,
}

OUTPUT.write_text(
    json.dumps(geojson, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print("Created:", OUTPUT)
print("Drainage features:", len(features))

types = {}
for feature in features:
    value = feature["properties"]["waterway"]
    types[value] = types.get(value, 0) + 1

print("Waterway types:", types)
