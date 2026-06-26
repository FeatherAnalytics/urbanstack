import csv
import io
import json
import logging
import zipfile
from pathlib import Path

import polars as pl
import requests
from pydantic import ValidationError

from urbanstack.config import Settings
from urbanstack.contracts.gtfs import GtfsRoute, GtfsShape, GtfsStop
from urbanstack.extract.transit_discovery import discover_feeds
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)


def _download_feed(feed_id: str, url: str, raw_dir: Path, *, force: bool) -> Path:
    zip_path = raw_dir / f"{feed_id}_gtfs.zip"
    if zip_path.exists() and not force:
        logger.info("GTFS zip exists, skipping download: %s", zip_path)
        return zip_path

    headers = {"User-Agent": "UrbanStack/1.0 (transit data pipeline)"}
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()
    zip_path.write_bytes(resp.content)
    logger.info("Downloaded %s GTFS to %s", feed_id, zip_path)
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


def _parse_routes(agency: str, rows: list[dict[str, str]], prefix: str = "") -> list[GtfsRoute]:
    records: list[GtfsRoute] = []
    for row in rows:
        route_type_raw = row.get("route_type", "3")
        try:
            route_type = int(route_type_raw)
        except (ValueError, TypeError):
            route_type = 3
        try:
            records.append(
                GtfsRoute.model_validate(
                    {
                        "agency": agency,
                        "route_id": f"{prefix}:{row['route_id']}" if prefix else row["route_id"],
                        "route_short_name": row.get("route_short_name", ""),
                        "route_long_name": row.get("route_long_name", ""),
                        "route_type": route_type,
                        "route_color": row.get("route_color", ""),
                    }
                )
            )
        except ValidationError:
            continue
    return records


def _parse_stops(agency: str, rows: list[dict[str, str]], prefix: str = "") -> list[GtfsStop]:
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
        try:
            records.append(
                GtfsStop.model_validate(
                    {
                        "agency": agency,
                        "stop_id": f"{prefix}:{row['stop_id']}" if prefix else row["stop_id"],
                        "stop_name": row.get("stop_name", ""),
                        "latitude": lat_f,
                        "longitude": lon_f,
                    }
                )
            )
        except ValidationError:
            continue
    return records


def _parse_shapes(agency: str, rows: list[dict[str, str]], prefix: str = "") -> list[GtfsShape]:
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
        try:
            records.append(
                GtfsShape.model_validate(
                    {
                        "agency": agency,
                        "shape_id": f"{prefix}:{row['shape_id']}" if prefix else row["shape_id"],
                        "latitude": lat_f,
                        "longitude": lon_f,
                        "sequence": seq_i,
                    }
                )
            )
        except ValidationError:
            continue
    return records


def _records_to_df(records: list) -> pl.DataFrame:
    if not records:
        return pl.DataFrame()
    return pl.DataFrame([r.model_dump() for r in records])


def extract_gtfs(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> dict[str, pl.DataFrame]:
    """Extract GTFS data for a metro's transit agencies via auto-discovery."""
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

    discovered = discover_feeds(settings, metro, force=force)

    all_routes: list[GtfsRoute] = []
    all_stops: list[GtfsStop] = []
    all_shapes: list[GtfsShape] = []
    feed_manifest: dict[str, str] = {}

    for feed in discovered:
        url = feed.download_url or feed.stable_url
        if not url:
            logger.warning("No download URL for %s (%s), skipping", feed.provider, feed.mdb_id)
            continue

        agency = feed.provider

        try:
            zip_path = _download_feed(feed.mdb_id, url, raw_dir, force=force)

            route_rows = _read_csv_from_zip(zip_path, "routes.txt")
            stop_rows = _read_csv_from_zip(zip_path, "stops.txt")
            shape_rows = _read_csv_from_zip(zip_path, "shapes.txt")
        except (requests.RequestException, zipfile.BadZipFile, OSError, UnicodeDecodeError) as exc:
            logger.warning("Skipping %s: %s", agency, exc)
            continue

        prefix = feed.mdb_id
        all_routes.extend(_parse_routes(agency, route_rows, prefix))
        all_stops.extend(_parse_stops(agency, stop_rows, prefix))
        all_shapes.extend(_parse_shapes(agency, shape_rows, prefix))
        feed_manifest[feed.mdb_id] = agency

        logger.info(
            "%s: %d routes, %d stops, %d shape points",
            agency,
            len(route_rows),
            len(stop_rows),
            len(shape_rows),
        )

    manifest_path = raw_dir / "feed_manifest.json"
    manifest_path.write_text(json.dumps(feed_manifest, indent=2))
    logger.info("Wrote feed manifest: %d feeds", len(feed_manifest))

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
