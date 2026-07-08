"""Extract county and block group boundary GeoJSON from Census TIGERweb API.

Fetches geometry from TIGERweb MapServer:
- Layer 82: county boundaries
- Layer 10: block group boundaries (paginated)

Output goes to ``settings.web_data_dir(metro_id)`` as ``counties.geojson``
and ``block_groups.geojson``.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from pathlib import Path

    from urbanstack.config import Settings
    from urbanstack.metro import MetroConfig

logger = logging.getLogger("urbanstack.extract.boundaries")

TIGERWEB_BASE = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_Current/MapServer"
)
COUNTY_LAYER = 82
BLOCK_GROUP_LAYER = 10

_USER_AGENT = "urbanstack/0.1"
_PAGE_SIZE = 5000


# ---------------------------------------------------------------------------
# GeoJSON normalization
# ---------------------------------------------------------------------------


def _normalize_geojson(geojson: dict) -> dict:
    """Ensure GEOID is a string and rename BASENAME → NAME."""
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geoid = props.get("GEOID")
        if geoid is not None:
            props["GEOID"] = str(geoid)
        if "BASENAME" in props:
            props["NAME"] = props["BASENAME"]
        feature["properties"] = props
    return geojson


# ---------------------------------------------------------------------------
# County boundaries (layer 82) — no pagination needed for metro-scale
# ---------------------------------------------------------------------------

_COUNTY_OUT_FIELDS = "GEOID,BASENAME,STATE,COUNTY,AREALAND"


def _fetch_counties(metro: MetroConfig) -> dict | None:
    url = f"{TIGERWEB_BASE}/{COUNTY_LAYER}/query"
    all_features: list[dict] = []

    for state_fips, counties in metro.states.items():
        county_list = ",".join(f"'{c}'" for c in counties.values())
        params = {
            "where": f"STATE='{state_fips}' AND COUNTY IN ({county_list})",
            "outFields": _COUNTY_OUT_FIELDS,
            "f": "geojson",
            "outSR": "4326",
        }
        logger.info(
            "Fetching county boundaries: state %s (%d counties)", state_fips, len(counties)
        )
        try:
            resp = requests.get(
                url, params=params, timeout=60, headers={"User-Agent": _USER_AGENT}
            )
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            all_features.extend(features)
            logger.info("  Got %d county features for state %s", len(features), state_fips)
        except (requests.RequestException, json.JSONDecodeError) as exc:
            logger.error("TIGERweb county request failed for state %s: %s", state_fips, exc)
            return None

    if all_features:
        return {"type": "FeatureCollection", "features": all_features}
    return None


# ---------------------------------------------------------------------------
# Block group boundaries (layer 10) — paginated
# ---------------------------------------------------------------------------

_BG_OUT_FIELDS = "GEOID,BASENAME,STATE,COUNTY,TRACT,BLKGRP"


def _fetch_block_group_page(
    url: str, state_fips: str, county_list: str, offset: int
) -> dict | None:
    params = {
        "where": f"STATE='{state_fips}' AND COUNTY IN ({county_list})",
        "outFields": _BG_OUT_FIELDS,
        "f": "geojson",
        "outSR": "4326",
        "resultRecordCount": str(_PAGE_SIZE),
        "resultOffset": str(offset),
    }
    try:
        resp = requests.get(
            url, params=params, timeout=120, headers={"User-Agent": _USER_AGENT}
        )
        resp.raise_for_status()
        data = resp.json()
        if "features" in data:
            return data
        return None
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.error("Block group page at offset %d failed: %s", offset, exc)
        return None


def _fetch_block_groups(metro: MetroConfig) -> dict | None:
    url = f"{TIGERWEB_BASE}/{BLOCK_GROUP_LAYER}/query"
    all_features: list[dict] = []

    for state_fips, counties in metro.states.items():
        county_list = ",".join(f"'{c}'" for c in counties.values())
        logger.info(
            "Fetching block group boundaries: state %s (%d counties)", state_fips, len(counties)
        )
        offset = 0

        while True:
            page = _fetch_block_group_page(url, state_fips, county_list, offset)
            if not page or "features" not in page:
                if offset == 0:
                    logger.warning("No block group data for state %s", state_fips)
                break

            features = page["features"]
            if not features:
                break

            all_features.extend(features)
            logger.info(
                "  offset=%d: %d features (total: %d)", offset, len(features), len(all_features)
            )

            if len(features) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE

    if all_features:
        return {"type": "FeatureCollection", "features": all_features}
    return None


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def _write_geojson(geojson: dict, path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(geojson, separators=(",", ":")))
    n = len(geojson.get("features", []))
    size = path.stat().st_size
    if size > 1_000_000:
        logger.info("Wrote %d %s to %s (%.1f MB)", n, label, path, size / 1e6)
    else:
        logger.info("Wrote %d %s to %s (%.0f KB)", n, label, path, size / 1024)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_boundaries(
    settings: Settings, metro: MetroConfig, *, force: bool = False
) -> None:
    """Fetch county and block group GeoJSON from TIGERweb for *metro*."""
    web_dir = settings.web_data_dir(metro.metro_id)

    # --- Counties ---
    county_path = web_dir / "counties.geojson"
    if county_path.exists() and not force:
        logger.info("Counties GeoJSON exists, skipping: %s", county_path)
    else:
        logger.info("Extracting county boundaries for %s", metro.metro_id)
        geojson = _fetch_counties(metro)
        if geojson is None:
            raise RuntimeError(
                f"Could not fetch county boundaries for {metro.metro_id}"
            )
        geojson = _normalize_geojson(geojson)
        _write_geojson(geojson, county_path, "counties")

    # --- Block groups ---
    bg_path = web_dir / "block_groups.geojson"
    if bg_path.exists() and not force:
        logger.info("Block groups GeoJSON exists, skipping: %s", bg_path)
    else:
        logger.info("Extracting block group boundaries for %s", metro.metro_id)
        geojson = _fetch_block_groups(metro)
        if geojson is None:
            raise RuntimeError(
                f"Could not fetch block group boundaries for {metro.metro_id}"
            )
        geojson = _normalize_geojson(geojson)
        _write_geojson(geojson, bg_path, "block groups")
