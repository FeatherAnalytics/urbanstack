import logging
import math

import polars as pl
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from urbanstack.config import Settings
from urbanstack.contracts.osm_parks import OSM_PARK_SCHEMA, PARK_TAGS, OsmParkRecord
from urbanstack.metro import MetroConfig
from urbanstack.transform.spatial import compute_bbox, load_boundaries

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT = 120


USER_AGENT = "UrbanStack/1.0 (https://github.com/FeatherAnalytics/urbanstack)"


def _overpass_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def _build_overpass_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    filters = [
        f'{elem}["{k}"="{v}"]({bbox_str});'
        for k, v in PARK_TAGS
        for elem in ("way", "relation")
    ]
    query_body = "\n  ".join(filters)
    return f"[out:json][timeout:{REQUEST_TIMEOUT}];\n(\n  {query_body}\n);\nout bb qt;\n"


def _bbox_area_sqm(bounds: dict) -> float:
    mid_lat = (bounds["minlat"] + bounds["maxlat"]) / 2
    height_m = (bounds["maxlat"] - bounds["minlat"]) * 111_320.0
    width_m = (bounds["maxlon"] - bounds["minlon"]) * 111_320.0 * math.cos(math.radians(mid_lat))
    return abs(height_m * width_m)


def _parse_element(element: dict) -> dict | None:
    tags = element.get("tags", {})
    park_type = next((v for k, v in PARK_TAGS if tags.get(k) == v), None)
    if not park_type:
        return None

    center = element.get("center")
    bounds = element.get("bounds")
    bounds_complete = bounds and all(
        k in bounds for k in ("minlat", "maxlat", "minlon", "maxlon")
    )

    if center and "lat" in center and "lon" in center:
        lat, lon = center["lat"], center["lon"]
    elif bounds_complete:
        lat = (bounds["minlat"] + bounds["maxlat"]) / 2
        lon = (bounds["minlon"] + bounds["maxlon"]) / 2
    else:
        return None

    area_sqm = _bbox_area_sqm(bounds) if bounds_complete else 0.0

    return {
        "osm_id": element.get("id"),
        "name": tags.get("name"),
        "park_type": park_type,
        "area_sqm": area_sqm,
        "centroid_lat": lat,
        "centroid_lon": lon,
    }


def _dedup_parks(records: list[dict]) -> list[dict]:
    # yagni: proximity dedup ~11m, upgrade to spatial index if needed
    best: dict[tuple[float, float, str], dict] = {}
    for r in records:
        key = (round(r["centroid_lat"], 4), round(r["centroid_lon"], 4), r["park_type"])
        prev = best.get(key)
        if prev is None or r["area_sqm"] > prev["area_sqm"]:
            best[key] = r
    deduped = list(best.values())
    if len(records) != len(deduped):
        logger.info("Deduped parks: %d → %d", len(records), len(deduped))
    return deduped


def _fetch_parks(bbox: tuple[float, float, float, float]) -> list[dict]:
    query = _build_overpass_query(bbox)
    logger.info("Querying Overpass API for parks in bbox %s", bbox)

    session = _overpass_session()
    resp = session.post(OVERPASS_URL, data={"data": query}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    elements = resp.json().get("elements", [])
    logger.info("Overpass returned %d elements", len(elements))

    records = [r for el in elements if (r := _parse_element(el)) is not None]
    return _dedup_parks(records)


def extract_osm_parks(
    settings: Settings, metro: MetroConfig, *, force: bool = False
) -> pl.DataFrame:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "osm_parks"
    parquet_path = parquet_dir / f"osm_parks_{metro.metro_id}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    geojson_path = settings.web_data_dir(metro.metro_id) / "counties.geojson"
    if not geojson_path.exists():
        raise FileNotFoundError(
            f"Counties GeoJSON not found: {geojson_path}. "
            "Run county mart first to generate GeoJSON boundaries."
        )

    boundaries = load_boundaries(geojson_path)
    bbox = compute_bbox(boundaries)
    records = _fetch_parks(bbox)

    validated = [OsmParkRecord.model_validate(r).model_dump() for r in records]
    df = (
        pl.DataFrame(validated, schema=OSM_PARK_SCHEMA)
        if validated
        else pl.DataFrame(schema=OSM_PARK_SCHEMA)
    )

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d parks for %s to %s", len(df), metro.metro_id, parquet_path)

    return df
