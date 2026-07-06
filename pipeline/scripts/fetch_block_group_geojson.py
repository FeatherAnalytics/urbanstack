"""Fetch block group boundary GeoJSON from Census TIGERweb API for any metro.

USAGE:
    python scripts/fetch_block_group_geojson.py --metro houston
    python scripts/fetch_block_group_geojson.py --metro all
"""

import argparse
import json
import sys
from pathlib import Path

import requests
import truststore

truststore.inject_into_ssl()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from urbanstack.metro import METRO_REGISTRY, MetroConfig  # noqa: E402

TIGERWEB_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_Current/MapServer/10/query"
)

PAGE_SIZE = 5000


def fetch_tigerweb_page(state_fips: str, county_list: str, offset: int) -> dict | None:
    params = {
        "where": f"STATE='{state_fips}' AND COUNTY IN ({county_list})",
        "outFields": "GEOID,BASENAME,STATE,COUNTY,TRACT,BLKGRP",
        "f": "geojson",
        "outSR": "4326",
        "resultRecordCount": str(PAGE_SIZE),
        "resultOffset": str(offset),
    }
    try:
        resp = requests.get(
            TIGERWEB_URL, params=params, timeout=120,
            headers={"User-Agent": "urbanstack/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "features" in data:
            return data
        return None
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"    Page at offset {offset} failed: {e}")
        return None


def fetch_tigerweb(metro: MetroConfig) -> dict | None:
    all_features: list[dict] = []

    for state_fips, counties in metro.states.items():
        county_list = ",".join(f"'{c}'" for c in counties.values())
        print(f"  State {state_fips} ({len(counties)} counties)...")
        offset = 0

        while True:
            page = fetch_tigerweb_page(state_fips, county_list, offset)
            if not page or "features" not in page:
                if offset == 0:
                    print(f"    No data for state {state_fips}")
                break

            features = page["features"]
            if not features:
                break

            all_features.extend(features)
            print(f"    offset={offset}: {len(features)} features (total: {len(all_features)})")

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


def fetch_metro(metro: MetroConfig, web_root: Path) -> bool:
    out_path = web_root / metro.metro_id / "counties.geojson"
    bg_path = web_root / metro.metro_id / "block_groups.geojson"
    if bg_path.exists():
        print(f"  Already exists: {bg_path}")
        return True

    print(f"Fetching block groups for {metro.metro_id}...")
    geojson = fetch_tigerweb(metro)
    if not geojson:
        print(f"ERROR: Could not fetch block group boundaries for {metro.metro_id}")
        return False

    geojson = normalize_geojson(geojson)
    bg_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path.write_text(json.dumps(geojson, separators=(",", ":")))
    n = len(geojson.get("features", []))
    mb = bg_path.stat().st_size / 1e6
    print(f"  Wrote {n} block groups to {bg_path} ({mb:.1f} MB)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch block group GeoJSON")
    parser.add_argument("--metro", required=True, choices=["all", *sorted(METRO_REGISTRY)])
    parser.add_argument("--web-root", default="../web/public/data", help="Web data directory")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    web_root = Path(args.web_root)
    metros = list(METRO_REGISTRY.values()) if args.metro == "all" else [METRO_REGISTRY[args.metro]]

    ok = True
    for metro in metros:
        if args.force:
            out = web_root / metro.metro_id / "block_groups.geojson"
            if out.exists():
                out.unlink()
        if not fetch_metro(metro, web_root):
            ok = False

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
