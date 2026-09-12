from pathlib import Path
import json
import urllib.parse
import urllib.request


OUTPUT = Path(
    "data/gis/villages/osm_settlements_mandi_pandoh.geojson"
)

query = """
[out:json][timeout:120];
nwr["place"~"^(city|town|village|hamlet)$"]
(31.60,76.85,31.80,77.15);
out center tags;
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

print("Downloading OSM settlements...")

with urllib.request.urlopen(
    request,
    timeout=180,
) as response:
    osm = json.load(response)

features = []

for element in osm.get("elements", []):
    tags = element.get("tags", {})

    if element["type"] == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        continue

    features.append(
        {
            "type": "Feature",
            "properties": {
                "osm_type": element["type"],
                "osm_id": element["id"],
                "name": tags.get("name"),
                "place": tags.get("place"),
                "population": tags.get("population"),
                "source": "OpenStreetMap / Overpass API",
                "license": "ODbL",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
        }
    )

geojson = {
    "type": "FeatureCollection",
    "name": "osm_settlements_mandi_pandoh",
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
print("Settlement features:", len(features))

types = {}

for feature in features:
    place_type = feature["properties"]["place"]
    types[place_type] = types.get(place_type, 0) + 1

print("Settlement types:", types)

named = sum(
    1 for feature in features
    if feature["properties"]["name"]
)

print("Named settlements:", named)
