#!/usr/bin/env python3
"""Download GTFS feeds and convert to GeoJSON for the web app.

USAGE:
    cd pipeline && uv run python scripts/build_transit_geojson.py

Runs the GTFS extractor to download real feeds from DART, Trinity Metro, DCTA,
then converts shape/route/stop data into GeoJSON files at:
    web/public/data/transit_routes.geojson
    web/public/data/transit_stops.geojson
"""

import json
import logging
import sys
from pathlib import Path

import polars as pl

from urbanstack.config import load_settings
from urbanstack.extract.gtfs import GTFS_FEEDS, _read_csv_from_zip, extract_gtfs

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# GTFS route_type codes
ROUTE_TYPE_LABELS: dict[int, str] = {
    0: "tram",
    1: "subway",
    2: "rail",
    3: "bus",
}

WEB_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "public" / "data"


def _load_trips_from_zips(raw_dir: Path, agencies: list[str]) -> pl.DataFrame:
    """Read trips.txt from each downloaded ZIP to get shape_id -> route_id mapping."""
    all_rows: list[dict[str, str]] = []
    for agency in agencies:
        zip_name = f"{agency.lower().replace(' ', '_')}_gtfs.zip"
        zip_path = raw_dir / zip_name
        if not zip_path.exists():
            logger.warning("ZIP not found for %s, skipping trips", agency)
            continue
        rows = _read_csv_from_zip(zip_path, "trips.txt")
        for row in rows:
            row["agency"] = agency
        all_rows.extend(rows)

    if not all_rows:
        return pl.DataFrame(schema={"agency": pl.Utf8, "route_id": pl.Utf8, "shape_id": pl.Utf8})

    df = pl.DataFrame(all_rows)
    cols_needed = ["agency", "route_id", "shape_id"]
    missing = [c for c in cols_needed if c not in df.columns]
    if missing:
        logger.error("trips.txt missing columns: %s", missing)
        return pl.DataFrame(schema={"agency": pl.Utf8, "route_id": pl.Utf8, "shape_id": pl.Utf8})

    return df.select(cols_needed).unique()


def _classify_mode(route_type: int) -> str:
    """Classify GTFS route_type into 'rail' or 'bus'."""
    # 0=tram, 1=subway, 2=rail → "rail"; everything else → "bus"
    return "rail" if route_type in (0, 1, 2) else "bus"


def _load_stop_modes(raw_dir: Path, agencies: list[str]) -> tuple[set[str], dict[str, set[str]]]:
    """Build stop_id → set of modes by chaining stop_times → trips → routes.

    Returns (active_stop_keys, stop_modes) where:
      - active_stop_keys: set of "agency::stop_id" strings
      - stop_modes: dict mapping "agency::stop_id" → set of mode strings ("rail", "bus")
    """
    active_stops: set[str] = set()
    stop_modes: dict[str, set[str]] = {}

    for agency in agencies:
        zip_name = f"{agency.lower().replace(' ', '_')}_gtfs.zip"
        zip_path = raw_dir / zip_name
        if not zip_path.exists():
            continue

        # 1. routes.txt → route_id → route_type
        route_type_map: dict[str, int] = {}
        for row in _read_csv_from_zip(zip_path, "routes.txt"):
            rid = row.get("route_id", "")
            try:
                rt = int(row.get("route_type", "3"))
            except ValueError:
                rt = 3
            if rid:
                route_type_map[rid] = rt

        # 2. trips.txt → trip_id → route_id
        trip_route_map: dict[str, str] = {}
        for row in _read_csv_from_zip(zip_path, "trips.txt"):
            tid = row.get("trip_id", "")
            rid = row.get("route_id", "")
            if tid and rid:
                trip_route_map[tid] = rid

        # 3. stop_times.txt → stop_id → trip_id → route_id → mode
        for row in _read_csv_from_zip(zip_path, "stop_times.txt"):
            sid = row.get("stop_id", "")
            tid = row.get("trip_id", "")
            if not sid:
                continue
            key = f"{agency}::{sid}"
            active_stops.add(key)

            rid = trip_route_map.get(tid, "")
            if rid:
                rt = route_type_map.get(rid, 3)
                mode = _classify_mode(rt)
                stop_modes.setdefault(key, set()).add(mode)

    return active_stops, stop_modes


def _pick_longest_shape(
    shapes_df: pl.DataFrame, trips_df: pl.DataFrame
) -> pl.DataFrame:
    """For each (agency, route_id), pick the shape_id with the most points."""
    # Count points per shape
    shape_counts = shapes_df.group_by(["agency", "shape_id"]).agg(
        pl.len().alias("point_count")
    )

    # Join trips to shape counts
    joined = trips_df.join(shape_counts, on=["agency", "shape_id"], how="inner")

    # Pick the shape with the most points per route
    best = (
        joined.sort("point_count", descending=True)
        .group_by(["agency", "route_id"])
        .first()
        .select(["agency", "route_id", "shape_id"])
    )
    return best


def _build_linestring(points: list[tuple[float, float]]) -> dict:
    """Build a GeoJSON LineString geometry from (lon, lat) tuples."""
    return {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in points]}


def build_routes_geojson(
    shapes_df: pl.DataFrame,
    routes_df: pl.DataFrame,
    trips_df: pl.DataFrame,
) -> dict:
    """Build GeoJSON FeatureCollection for transit routes."""
    if shapes_df.is_empty() or routes_df.is_empty() or trips_df.is_empty():
        return {"type": "FeatureCollection", "features": []}

    best_shapes = _pick_longest_shape(shapes_df, trips_df)

    # Join route metadata
    route_shapes = best_shapes.join(routes_df, on=["agency", "route_id"], how="inner")

    features: list[dict] = []
    for row in route_shapes.iter_rows(named=True):
        agency = row["agency"]
        shape_id = row["shape_id"]
        route_name = row.get("route_short_name") or row.get("route_long_name") or ""
        route_long = row.get("route_long_name") or ""
        route_type = row.get("route_type", 3)

        # Get shape points sorted by sequence
        shape_points = (
            shapes_df.filter(
                (pl.col("agency") == agency) & (pl.col("shape_id") == shape_id)
            )
            .sort("sequence")
        )

        if shape_points.is_empty():
            continue

        coords = list(
            zip(
                shape_points["longitude"].to_list(),
                shape_points["latitude"].to_list(),
            )
        )

        if len(coords) < 2:
            continue

        # Build display name
        display_name = route_name
        if route_long and route_long != route_name:
            display_name = f"{route_name} - {route_long}" if route_name else route_long

        route_type_label = ROUTE_TYPE_LABELS.get(route_type, "other")
        raw_color = row.get("route_color", "")
        color = f"#{raw_color}" if raw_color and not raw_color.startswith("#") else raw_color

        feature = {
            "type": "Feature",
            "properties": {
                "agency": agency,
                "route_name": display_name,
                "route_type": route_type_label,
                "route_type_code": route_type,
                "color": color or "",
            },
            "geometry": _build_linestring(coords),
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def build_stops_geojson(
    stops_df: pl.DataFrame,
    active_stop_keys: set[str],
    stop_modes: dict[str, set[str]],
) -> dict:
    """Build GeoJSON FeatureCollection for transit stops.

    Filters to only stops appearing in stop_times.txt (active stops).
    If active_stop_keys is empty, includes all stops.
    Each stop gets a ``modes`` property: ["rail"], ["bus"], or ["rail", "bus"].
    """
    if stops_df.is_empty():
        return {"type": "FeatureCollection", "features": []}

    features: list[dict] = []
    for row in stops_df.iter_rows(named=True):
        agency = row["agency"]
        stop_id = row["stop_id"]
        key = f"{agency}::{stop_id}"

        # Filter to active stops if we have the data
        if active_stop_keys and key not in active_stop_keys:
            continue

        modes = sorted(stop_modes.get(key, {"bus"}))

        feature = {
            "type": "Feature",
            "properties": {
                "agency": agency,
                "stop_name": row.get("stop_name", ""),
                "modes": modes,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def _count_by_agency(features: list[dict], label: str) -> None:
    """Log counts grouped by agency."""
    counts: dict[str, int] = {}
    for f in features:
        agency = f.get("properties", {}).get("agency", "unknown")
        counts[agency] = counts.get(agency, 0) + 1
    for agency, count in sorted(counts.items()):
        logger.info("  %s: %d %s", agency, count, label)


def _count_by_mode(features: list[dict]) -> None:
    """Log stop counts grouped by mode combination."""
    counts: dict[str, int] = {}
    for f in features:
        modes = f.get("properties", {}).get("modes", [])
        key = "+".join(modes) if modes else "unknown"
        counts[key] = counts.get(key, 0) + 1
    for mode_key, count in sorted(counts.items()):
        logger.info("  %s: %d stops", mode_key, count)


def main() -> int:
    settings = load_settings()
    settings.ensure_dirs()

    # Step 1: Download and extract GTFS feeds
    logger.info("Extracting GTFS feeds...")
    succeeded_agencies: list[str] = []
    failed_agencies: list[str] = []

    # Try each agency individually so failures don't block others
    all_routes = pl.DataFrame()
    all_stops = pl.DataFrame()
    all_shapes = pl.DataFrame()

    for agency in GTFS_FEEDS:
        try:
            result = extract_gtfs(settings, agencies=[agency], force=True)
            r, s, sh = result["routes"], result["stops"], result["shapes"]
            if not r.is_empty():
                all_routes = pl.concat([all_routes, r]) if not all_routes.is_empty() else r
            if not s.is_empty():
                all_stops = pl.concat([all_stops, s]) if not all_stops.is_empty() else s
            if not sh.is_empty():
                all_shapes = pl.concat([all_shapes, sh]) if not all_shapes.is_empty() else sh
            succeeded_agencies.append(agency)
            logger.info("OK: %s", agency)
        except Exception:
            logger.exception("FAILED: %s — skipping", agency)
            failed_agencies.append(agency)

    if not succeeded_agencies:
        logger.error("All agencies failed. No GeoJSON generated.")
        return 1

    if failed_agencies:
        logger.warning("Skipped agencies: %s", ", ".join(failed_agencies))

    # Step 2: Load trips.txt for shape_id -> route_id mapping
    logger.info("Loading trips.txt from ZIPs...")
    raw_dir = settings.raw_dir / "gtfs"
    trips_df = _load_trips_from_zips(raw_dir, succeeded_agencies)
    logger.info("Trips: %d unique (agency, route_id, shape_id) rows", len(trips_df))

    # Step 3: Load active stop IDs and mode classification from GTFS
    logger.info("Loading stop_times/trips/routes for stop modes...")
    active_stops, stop_modes = _load_stop_modes(raw_dir, succeeded_agencies)
    logger.info("Active stop keys: %d", len(active_stops))

    # Step 4: Build routes GeoJSON
    logger.info("Building routes GeoJSON...")
    routes_geojson = build_routes_geojson(all_shapes, all_routes, trips_df)
    route_count = len(routes_geojson["features"])
    logger.info("Routes: %d total", route_count)
    _count_by_agency(routes_geojson["features"], "routes")

    # Step 5: Build stops GeoJSON
    logger.info("Building stops GeoJSON...")
    stops_geojson = build_stops_geojson(all_stops, active_stops, stop_modes)
    stop_count = len(stops_geojson["features"])
    logger.info("Stops: %d total", stop_count)
    _count_by_agency(stops_geojson["features"], "stops")
    _count_by_mode(stops_geojson["features"])

    # Step 6: Write output
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    routes_path = WEB_DATA_DIR / "transit_routes.geojson"
    stops_path = WEB_DATA_DIR / "transit_stops.geojson"

    routes_path.write_text(json.dumps(routes_geojson))
    stops_path.write_text(json.dumps(stops_geojson))

    routes_kb = routes_path.stat().st_size / 1024
    stops_kb = stops_path.stat().st_size / 1024

    logger.info("Wrote %s (%.0f KB, %d routes)", routes_path, routes_kb, route_count)
    logger.info("Wrote %s (%.0f KB, %d stops)", stops_path, stops_kb, stop_count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
