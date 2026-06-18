"""Fetch DFW county boundary GeoJSON from Census TIGERweb API.

USAGE:
    python scripts/fetch_county_geojson.py --output ../web/public/data/dfw_counties.geojson

Falls back to plotly dataset if TIGERweb is unavailable.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

DFW_FIPS = [
    "48085", "48113", "48121", "48139", "48221", "48231",
    "48251", "48257", "48367", "48397", "48439", "48497",
]

COUNTY_CODES = [fips[2:] for fips in DFW_FIPS]

TIGERWEB_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_Current/MapServer/82/query"
)

PLOTLY_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/"
    "geojson-counties-fips.json"
)


def fetch_tigerweb() -> dict | None:
    """Try TIGERweb REST API first (smaller payload, exact counties)."""
    county_list = ",".join(f"'{c}'" for c in COUNTY_CODES)
    params = (
        f"where=STATE%3D'48'+AND+COUNTY+IN+({county_list})"
        f"&outFields=GEOID,BASENAME,STATE,COUNTY,AREALAND"
        f"&f=geojson&outSR=4326"
    )
    url = f"{TIGERWEB_URL}?{params}"
    print(f"Trying TIGERweb: {url[:120]}...")
    try:
        req = Request(url, headers={"User-Agent": "urbanstack/0.1"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if "features" in data and len(data["features"]) > 0:
            print(f"  Got {len(data['features'])} features from TIGERweb")
            return data
        print("  TIGERweb returned no features")
        return None
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"  TIGERweb failed: {e}")
        return None


def fetch_plotly() -> dict | None:
    """Fallback: download full US counties GeoJSON and filter to DFW."""
    print(f"Trying plotly fallback (19MB download)...")
    try:
        req = Request(PLOTLY_URL, headers={"User-Agent": "urbanstack/0.1"})
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
        dfw_features = [
            f for f in data["features"]
            if f.get("id") in DFW_FIPS
               or f.get("properties", {}).get("GEO_ID", "")[-5:] in DFW_FIPS
        ]
        if dfw_features:
            print(f"  Filtered to {len(dfw_features)} DFW counties from plotly")
            return {"type": "FeatureCollection", "features": dfw_features}
        print("  No matching features in plotly dataset")
        return None
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"  Plotly fallback failed: {e}")
        return None


def normalize_geojson(geojson: dict) -> dict:
    """Ensure each feature has a GEOID property matching our FIPS codes."""
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        # TIGERweb uses GEOID directly
        geoid = props.get("GEOID")
        # Plotly uses id at feature level
        if not geoid and feature.get("id"):
            geoid = feature["id"]
        # Plotly GEO_ID format: 0500000US48113
        if not geoid:
            geo_id = props.get("GEO_ID", "")
            if geo_id and len(geo_id) >= 5:
                geoid = geo_id[-5:]
        if geoid:
            props["GEOID"] = geoid
            # Add county name from BASENAME if available
            if "BASENAME" in props:
                props["NAME"] = props["BASENAME"]
        feature["properties"] = props
    return geojson


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch DFW county GeoJSON")
    parser.add_argument(
        "--output", "-o",
        default="../web/public/data/dfw_counties.geojson",
        help="Output file path",
    )
    args = parser.parse_args()

    geojson = fetch_tigerweb()
    if not geojson:
        geojson = fetch_plotly()
    if not geojson:
        print("ERROR: Could not fetch county boundaries from any source")
        sys.exit(1)

    geojson = normalize_geojson(geojson)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(geojson, separators=(",", ":")))
    feature_count = len(geojson.get("features", []))
    size_kb = out_path.stat().st_size / 1024
    print(f"Wrote {feature_count} counties to {out_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
