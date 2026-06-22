import json
import logging
from pathlib import Path

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.tmas_stations import TmasStationRecord
from urbanstack.metro import FIPS_TO_ABBR, MetroConfig

logger = logging.getLogger(__name__)

ARCGIS_URL = (
    "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
    "NTAD_Travel_Monitoring_Analysis_System_Stations/FeatureServer/0/query"
)


def _point_in_polygon(
    px: float, py: float, ring: list[list[float]]
) -> bool:
    """Ray-casting point-in-polygon test."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def _load_county_polygons(geojson_path: Path) -> list[dict]:
    """Load county boundaries from GeoJSON. Returns list of {fips, rings}."""
    with open(geojson_path) as f:
        geo = json.load(f)

    counties: list[dict] = []
    for feat in geo["features"]:
        fips = feat["properties"]["GEOID"]
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            rings = geom["coordinates"]
        elif geom["type"] == "MultiPolygon":
            rings = [ring for poly in geom["coordinates"] for ring in poly]
        else:
            continue
        counties.append({"fips": fips, "rings": rings})
    return counties


def _assign_county(
    lon: float, lat: float, counties: list[dict]
) -> str | None:
    """Return county FIPS if point falls within any metro county."""
    for county in counties:
        for ring in county["rings"]:
            if _point_in_polygon(lon, lat, ring):
                return county["fips"]
    return None


def _fetch_stations(state_abbr: str) -> list[dict]:
    """Fetch TMAS stations for a state from ArcGIS Feature Service."""
    params = {
        "where": f"state='{state_abbr}'",
        "outFields": "Station_Id,latitude,longitude,functional_class",
        "resultRecordCount": "2000",
        "f": "json",
    }
    resp = requests.get(ARCGIS_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if "features" not in data:
        raise ValueError(f"Unexpected ArcGIS response: {list(data.keys())}")
    return [f["attributes"] for f in data["features"]]


def extract_tmas_stations(
    settings: Settings, metro: MetroConfig, *, force: bool = False
) -> pl.DataFrame:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "tmas_stations"
    parquet_path = parquet_dir / f"tmas_stations_{metro.metro_id}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    raw_stations: list[dict] = []
    for state_fips in sorted(metro.state_fips_set):
        abbr = FIPS_TO_ABBR.get(state_fips)
        if not abbr:
            logger.warning("No abbreviation for state FIPS %s — skipping TMAS", state_fips)
            continue
        raw_stations.extend(_fetch_stations(abbr))

    logger.info("Fetched %d stations for %s from ArcGIS", len(raw_stations), metro.metro_id)

    raw_dir = settings.metro_raw_dir(metro.metro_id) / "tmas_stations"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"tmas_stations_{metro.metro_id}.json").write_text(
        json.dumps(raw_stations, indent=2)
    )

    geojson_path = (
        Path(settings.data_dir).resolve().parent.parent
        / "web"
        / "public"
        / "data"
        / metro.metro_id
        / "counties.geojson"
    )
    counties = _load_county_polygons(geojson_path)

    records: list[TmasStationRecord] = []
    for stn in raw_stations:
        lat = stn.get("latitude")
        lon = stn.get("longitude")
        if lat is None or lon is None:
            continue
        fips = _assign_county(float(lon), float(lat), counties)
        if fips is None:
            continue
        sid = str(stn.get("Station_Id", "")).strip()
        if not sid:
            continue
        records.append(
            TmasStationRecord(
                station_id=sid,
                county_fips=fips,
                latitude=float(lat),
                longitude=float(lon),
                functional_class=stn.get("functional_class"),
            )
        )

    logger.info("Matched %d stations to %s counties", len(records), metro.metro_name)

    df = pl.DataFrame([r.model_dump() for r in records])
    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
