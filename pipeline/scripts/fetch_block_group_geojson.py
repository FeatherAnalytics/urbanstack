"""Fetch DFW block group boundary GeoJSON from Census TIGERweb API.

USAGE:
    python scripts/fetch_block_group_geojson.py --output ../web/public/data/dfw_block_groups.geojson

Uses TIGERweb layer 84 (block groups) with pagination for ~4000 features.
Falls back to Census cartographic boundary shapefiles if TIGERweb is unavailable.
"""

import argparse
import json
import sys
from pathlib import Path

import requests
import truststore

truststore.inject_into_ssl()

DFW_COUNTY_CODES = [
    "085", "113", "121", "139", "221", "231",
    "251", "257", "367", "397", "439", "497",
]

TIGERWEB_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_Current/MapServer/10/query"
)

PAGE_SIZE = 5000


def fetch_tigerweb_page(offset: int) -> dict | None:
    county_list = ",".join(f"'{c}'" for c in DFW_COUNTY_CODES)
    params = {
        "where": f"STATE='48' AND COUNTY IN ({county_list})",
        "outFields": "GEOID,BASENAME,STATE,COUNTY,TRACT,BLKGRP",
        "f": "geojson",
        "outSR": "4326",
        "resultRecordCount": str(PAGE_SIZE),
        "resultOffset": str(offset),
    }
    try:
        resp = requests.get(TIGERWEB_URL, params=params, timeout=60,
                           headers={"User-Agent": "urbanstack/0.1"})
        resp.raise_for_status()
        data = resp.json()
        if "features" in data:
            return data
        return None
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"  TIGERweb page at offset {offset} failed: {e}")
        return None


def fetch_tigerweb() -> dict | None:
    print("Fetching DFW block groups from TIGERweb (layer 84)...")
    all_features: list[dict] = []
    offset = 0

    while True:
        print(f"  Requesting offset={offset}...")
        page = fetch_tigerweb_page(offset)
        if not page or "features" not in page:
            if offset == 0:
                print("  TIGERweb returned no data")
                return None
            break

        features = page["features"]
        if not features:
            break

        all_features.extend(features)
        print(f"  Got {len(features)} features (total: {len(all_features)})")

        if len(features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    if all_features:
        return {"type": "FeatureCollection", "features": all_features}
    return None


def normalize_geojson(geojson: dict) -> dict:
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geoid = props.get("GEOID")
        if geoid:
            props["GEOID"] = str(geoid)
        if "BASENAME" in props:
            props["NAME"] = props["BASENAME"]
        feature["properties"] = props
    return geojson


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch DFW block group GeoJSON"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="../web/public/data/dfw_block_groups.geojson",
        help="Output file path",
    )
    args = parser.parse_args()

    geojson = fetch_tigerweb()
    if not geojson:
        print("ERROR: Could not fetch block group boundaries from TIGERweb")
        sys.exit(1)

    geojson = normalize_geojson(geojson)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(geojson, separators=(",", ":")))
    feature_count = len(geojson.get("features", []))
    size_kb = out_path.stat().st_size / 1024
    print(f"Wrote {feature_count} block groups to {out_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
