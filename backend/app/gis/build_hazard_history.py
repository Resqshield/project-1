from pathlib import Path
import json


SETTLEMENTS = Path(
    "data/gis/villages/osm_settlements_mandi_pandoh.geojson"
)

OUTPUT = Path(
    "data/gis/hazard_history/"
    "verified_hazard_history_mandi_pandoh_2023.geojson"
)

settlement_data = json.loads(
    SETTLEMENTS.read_text(encoding="utf-8")
)


def find_settlement(name):
    target = name.casefold()

    exact = [
        feature
        for feature in settlement_data["features"]
        if (
            feature.get("properties", {}).get("name")
            and feature["properties"]["name"].strip().casefold()
            == target
        )
    ]

    matches = exact

    if not matches:
        matches = [
            feature
            for feature in settlement_data["features"]
            if (
                feature.get("properties", {}).get("name")
                and target
                in feature["properties"]["name"].strip().casefold()
            )
        ]

    if not matches:
        raise RuntimeError(
            f"Settlement not found in OSM layer: {name}"
        )

    priority = {
        "city": 0,
        "town": 1,
        "village": 2,
        "hamlet": 3,
    }

    matches.sort(
        key=lambda feature: priority.get(
            feature["properties"].get("place"),
            99,
        )
    )

    return matches[0]


mandi = find_settlement("Mandi")
pandoh = find_settlement("Pandoh")

print(
    "Mandi anchor:",
    mandi["properties"].get("name"),
    mandi["properties"].get("place"),
    mandi["geometry"]["coordinates"],
)

print(
    "Pandoh anchor:",
    pandoh["properties"].get("name"),
    pandoh["properties"].get("place"),
    pandoh["geometry"]["coordinates"],
)


features = [
    {
        "type": "Feature",
        "properties": {
            "event_id": "HP_MANDI_PANDOH_FLOOD_2023_07",
            "hazard_type": "flood",
            "start_date": "2023-07-07",
            "end_date": "2023-07-11",
            "location_name": "Pandoh, Mandi, Himachal Pradesh",
            "event_status": "VERIFIED",
            "evidence_source": (
                "Himachal Pradesh State Disaster Management "
                "Authority, Post Disaster Needs Assessment "
                "Monsoon 2023; Sphere India Himachal Pradesh "
                "Floods July 2023 assessment"
            ),
            "evidence_note": (
                "July 7-11 2023 extreme rainfall/flood spell; "
                "Pandoh, Mandi documented as significantly "
                "affected by flooding."
            ),
            "geometry_source": "OpenStreetMap settlement layer",
            "geometry_precision": "Pandoh settlement centroid",
            "pilot_id": "HP_MANDI_PANDOH_CORRIDOR",
        },
        "geometry": pandoh["geometry"],
    },
    {
        "type": "Feature",
        "properties": {
            "event_id": "HP_MANDI_TARNA_LANDSLIDE_2023_08_14",
            "hazard_type": "landslide",
            "start_date": "2023-08-14",
            "end_date": "2023-08-14",
            "location_name": "Tarna Hill, Mandi, Himachal Pradesh",
            "event_status": "VERIFIED",
            "evidence_source": (
                "Geological Survey of India, Landslides in "
                "Mandi District, Himachal Pradesh on July, "
                "August and September 2023"
            ),
            "evidence_note": (
                "GSI reports a debris slide near HPPWD "
                "Circuit House at Tarna Hill on 14 August 2023."
            ),
            "geometry_source": "OpenStreetMap settlement layer",
            "geometry_precision": (
                "Mandi settlement centroid; Tarna Hill event "
                "location represented approximately"
            ),
            "pilot_id": "HP_MANDI_PANDOH_CORRIDOR",
        },
        "geometry": mandi["geometry"],
    },
]


geojson = {
    "type": "FeatureCollection",
    "name": "verified_hazard_history_mandi_pandoh_2023",
    "crs": {
        "type": "name",
        "properties": {
            "name": "EPSG:4326"
        },
    },
    "metadata": {
        "pilot_id": "HP_MANDI_PANDOH_CORRIDOR",
        "scope": "Verified historical flood and landslide replay events",
        "geometry_note": (
            "Event evidence and geometry are separate: "
            "event occurrence comes from authoritative reports; "
            "OSM settlement centroids provide spatial anchors."
        ),
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
print("Hazard events:", len(features))
print(
    "Hazard types:",
    sorted(
        feature["properties"]["hazard_type"]
        for feature in features
    ),
)
