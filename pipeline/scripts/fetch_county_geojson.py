"""Fetch county boundary GeoJSON from Census TIGERweb API for any metro.

USAGE:
    python scripts/fetch_county_geojson.py --metro houston
    python scripts/fetch_county_geojson.py --metro all
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
    "TIGERweb/tigerWMS_Current/MapServer/82/query"
)


def fetch_tigerweb(metro: MetroConfig) -> dict | None:
    all_features: list[dict] = []

    for state_fips, counties in metro.states.items():
        county_list = ",".join(f"'{c}'" for c in counties.values())
        params = {
            "where": f"STATE='{state_fips}' AND COUNTY IN ({county_list})",
            "outFields": "GEOID,BASENAME,STATE,COUNTY,AREALAND",
            "f": "geojson",
            "outSR": "4326",
        }
        print(f"  Fetching state {state_fips} ({len(counties)} counties)...")
        try:
            resp = requests.get(
                TIGERWEB_URL, params=params, timeout=60,
                headers={"User-Agent": "urbanstack/0.1"},
            )
            resp.raise_for_status()
            data = resp.json()
            if "features" in data:
                all_features.extend(data["features"])
                print(f"  Got {len(data['features'])} features")
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"  TIGERweb failed for state {state_fips}: {e}")
            return None

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
    if out_path.exists():
        print(f"  Already exists: {out_path}")
        return True

    print(f"Fetching counties for {metro.metro_id}...")
    geojson = fetch_tigerweb(metro)
    if not geojson:
        print(f"ERROR: Could not fetch county boundaries for {metro.metro_id}")
        return False

    geojson = normalize_geojson(geojson)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(geojson, separators=(",", ":")))
    n = len(geojson.get("features", []))
    kb = out_path.stat().st_size / 1024
    print(f"  Wrote {n} counties to {out_path} ({kb:.0f} KB)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch county GeoJSON")
    parser.add_argument("--metro", required=True, choices=["all", *sorted(METRO_REGISTRY)])
    parser.add_argument("--web-root", default="../web/public/data", help="Web data directory")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    web_root = Path(args.web_root)
    metros = list(METRO_REGISTRY.values()) if args.metro == "all" else [METRO_REGISTRY[args.metro]]

    ok = True
    for metro in metros:
        if args.force:
            out = web_root / metro.metro_id / "counties.geojson"
            if out.exists():
                out.unlink()
        if not fetch_metro(metro, web_root):
            ok = False

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
