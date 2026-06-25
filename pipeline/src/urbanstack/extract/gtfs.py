import csv
import io
import logging
import zipfile
from pathlib import Path

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.gtfs import GtfsRoute, GtfsShape, GtfsStop
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)


def _download_feed(agency: str, url: str, raw_dir: Path, *, force: bool) -> Path:
    zip_path = raw_dir / f"{agency.lower().replace(' ', '_')}_gtfs.zip"
    if zip_path.exists() and not force:
        logger.info("GTFS zip exists, skipping download: %s", zip_path)
        return zip_path

    headers = {"User-Agent": "UrbanStack/1.0 (transit data pipeline)"}
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()
    zip_path.write_bytes(resp.content)
    logger.info("Downloaded %s GTFS to %s", agency, zip_path)
    return zip_path


def _read_csv_from_zip(zip_path: Path, filename: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        match = None
        for name in names:
            if name == filename:
                match = name
                break
        if match is None:
            for name in names:
                if name.endswith("/" + filename):
                    match = name
                    break
        if match is None:
            return []
        with zf.open(match) as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig")
            reader = csv.DictReader(text)
            return list(reader)


def _parse_routes(agency: str, rows: list[dict[str, str]]) -> list[GtfsRoute]:
    records: list[GtfsRoute] = []
    for row in rows:
        route_type_raw = row.get("route_type", "3")
        try:
            route_type = int(route_type_raw)
        except (ValueError, TypeError):
            route_type = 3
        records.append(
            GtfsRoute.model_validate(
                {
                    "agency": agency,
                    "route_id": row["route_id"],
                    "route_short_name": row.get("route_short_name", ""),
                    "route_long_name": row.get("route_long_name", ""),
                    "route_type": route_type,
                    "route_color": row.get("route_color", ""),
                }
            )
        )
    return records


def _parse_stops(agency: str, rows: list[dict[str, str]]) -> list[GtfsStop]:
    records: list[GtfsStop] = []
    for row in rows:
        lat = row.get("stop_lat")
        lon = row.get("stop_lon")
        if lat is None or lon is None:
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            continue
        if lat_f == 0.0 and lon_f == 0.0:
            continue
        records.append(
            GtfsStop.model_validate(
                {
                    "agency": agency,
                    "stop_id": row["stop_id"],
                    "stop_name": row.get("stop_name", ""),
                    "latitude": lat_f,
                    "longitude": lon_f,
                }
            )
        )
    return records


def _parse_shapes(agency: str, rows: list[dict[str, str]]) -> list[GtfsShape]:
    records: list[GtfsShape] = []
    for row in rows:
        lat = row.get("shape_pt_lat")
        lon = row.get("shape_pt_lon")
        seq = row.get("shape_pt_sequence")
        if lat is None or lon is None or seq is None:
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            seq_i = int(seq)
        except (ValueError, TypeError):
            continue
        records.append(
            GtfsShape.model_validate(
                {
                    "agency": agency,
                    "shape_id": row["shape_id"],
                    "latitude": lat_f,
                    "longitude": lon_f,
                    "sequence": seq_i,
                }
            )
        )
    return records


def _records_to_df(records: list) -> pl.DataFrame:
    if not records:
        return pl.DataFrame()
    return pl.DataFrame([r.model_dump() for r in records])


def extract_gtfs(
    settings: Settings,
    metro: MetroConfig,
    agencies: list[str] | None = None,
    *,
    force: bool = False,
) -> dict[str, pl.DataFrame]:
    """Extract GTFS data for a metro's transit agencies.

    Returns dict with keys: "routes", "stops", "shapes" -- each a polars DataFrame.
    """
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "gtfs"
    routes_path = parquet_dir / "gtfs_routes.parquet"
    stops_path = parquet_dir / "gtfs_stops.parquet"
    shapes_path = parquet_dir / "gtfs_shapes.parquet"

    if all(p.exists() for p in (routes_path, stops_path, shapes_path)) and not force:
        logger.info("GTFS parquets exist, skipping extraction")
        return {
            "routes": pl.read_parquet(routes_path),
            "stops": pl.read_parquet(stops_path),
            "shapes": pl.read_parquet(shapes_path),
        }

    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    feed_list = agencies or list(metro.gtfs_feeds.keys())

    all_routes: list[GtfsRoute] = []
    all_stops: list[GtfsStop] = []
    all_shapes: list[GtfsShape] = []

    for agency in feed_list:
        url = metro.gtfs_feeds.get(agency)
        if url is None:
            raise ValueError(
                f"Unknown agency '{agency}'. Available: {list(metro.gtfs_feeds.keys())}"
            )

        try:
            zip_path = _download_feed(agency, url, raw_dir, force=force)

            route_rows = _read_csv_from_zip(zip_path, "routes.txt")
            stop_rows = _read_csv_from_zip(zip_path, "stops.txt")
            shape_rows = _read_csv_from_zip(zip_path, "shapes.txt")
        except (requests.RequestException, zipfile.BadZipFile, OSError, UnicodeDecodeError) as exc:
            logger.warning("Skipping %s: %s", agency, exc)
            continue

        all_routes.extend(_parse_routes(agency, route_rows))
        all_stops.extend(_parse_stops(agency, stop_rows))
        all_shapes.extend(_parse_shapes(agency, shape_rows))

        logger.info(
            "%s: %d routes, %d stops, %d shape points",
            agency,
            len(route_rows),
            len(stop_rows),
            len(shape_rows),
        )

    routes_df = _records_to_df(all_routes)
    stops_df = _records_to_df(all_stops)
    shapes_df = _records_to_df(all_shapes)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    if len(routes_df) > 0:
        routes_df.write_parquet(routes_path)
    if len(stops_df) > 0:
        stops_df.write_parquet(stops_path)
    if len(shapes_df) > 0:
        shapes_df.write_parquet(shapes_path)

    logger.info(
        "GTFS totals: %d routes, %d stops, %d shape points",
        len(routes_df),
        len(stops_df),
        len(shapes_df),
    )

    return {
        "routes": routes_df,
        "stops": stops_df,
        "shapes": shapes_df,
    }
