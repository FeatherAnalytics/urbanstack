#!/usr/bin/env python3
"""Download GTFS feeds and convert to GeoJSON for the web app.

USAGE:
    cd pipeline && uv run python scripts/build_transit_geojson.py [--metro METRO_ID] [--force]

Runs the GTFS extractor to download real feeds using transit discovery,
then converts shape/route/stop data into GeoJSON files at:
    web/public/data/{metro_id}/transit_routes.geojson
    web/public/data/{metro_id}/transit_stops.geojson
"""

import json
import logging
import sys
import zipfile
from pathlib import Path

import polars as pl

from urbanstack.config import load_settings
from urbanstack.extract.gtfs import _read_csv_from_zip, extract_gtfs

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# GTFS route_type codes
ROUTE_TYPE_LABELS: dict[int, str] = {
    0: "tram",
    1: "subway",
    2: "rail",
    3: "bus",
    4: "ferry",
}

WEB_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "public" / "data"


def _load_feed_manifest(raw_dir: Path) -> dict[str, str]:
    """Load mdb_id → provider name mapping from feed_manifest.json."""
    manifest_path = raw_dir / "feed_manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text())


def _load_trips_from_zips(raw_dir: Path, agencies: list[str]) -> pl.DataFrame:
    """Read trips.txt from all ZIPs using feed manifest for agency mapping."""
    manifest = _load_feed_manifest(raw_dir)
    agency_set = set(agencies)

    all_rows: list[dict[str, str]] = []
    for zip_path in sorted(raw_dir.glob("*.zip")):
        feed_id = zip_path.stem.replace("_gtfs", "")
        agency_name = manifest.get(feed_id, "")
        if not agency_name or agency_name not in agency_set:
            continue
        try:
            rows = _read_csv_from_zip(zip_path, "trips.txt")
        except (zipfile.BadZipFile, OSError):
            continue
        if not rows:
            continue
        for row in rows:
            row["agency"] = agency_name
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
    """Classify GTFS route_type into 'rail', 'ferry', or 'bus'."""
    # 0=tram, 1=subway, 2=rail → "rail"; 4=ferry → "ferry"; everything else → "bus"
    if route_type in (0, 1, 2):
        return "rail"
    if route_type == 4:
        return "ferry"
    return "bus"


def _load_stop_modes(raw_dir: Path, agencies: list[str]) -> tuple[set[str], dict[str, set[str]]]:
    """Build stop_id → set of modes by chaining stop_times → trips → routes.

    Returns (active_stop_keys, stop_modes) where:
      - active_stop_keys: set of "agency::stop_id" strings
      - stop_modes: dict mapping "agency::stop_id" → set of mode strings ("rail", "bus")
    """
    active_stops: set[str] = set()
    stop_modes: dict[str, set[str]] = {}

    manifest = _load_feed_manifest(raw_dir)
    agency_set = set(agencies)
    for zip_path in sorted(raw_dir.glob("*.zip")):
        feed_id = zip_path.stem.replace("_gtfs", "")
        agency = manifest.get(feed_id, "")
        if not agency or agency not in agency_set:
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


def _stops_for_routes(
    raw_dir: Path,
    agencies: list[str],
    rendered_routes: set[tuple[str, str]],
) -> set[str]:
    """Find stop keys served by a specific set of (agency, route_id) pairs."""
    manifest = _load_feed_manifest(raw_dir)
    agency_set = set(agencies)
    stop_keys: set[str] = set()

    for zip_path in sorted(raw_dir.glob("*.zip")):
        feed_id = zip_path.stem.replace("_gtfs", "")
        agency = manifest.get(feed_id, "")
        if not agency or agency not in agency_set:
            continue

        try:
            trip_rows = _read_csv_from_zip(zip_path, "trips.txt")
            st_rows = _read_csv_from_zip(zip_path, "stop_times.txt")
        except (zipfile.BadZipFile, OSError):
            continue

        route_trips: set[str] = set()
        for row in trip_rows:
            rid = row.get("route_id", "")
            if (agency, rid) in rendered_routes:
                route_trips.add(row.get("trip_id", ""))

        for row in st_rows:
            if row.get("trip_id", "") in route_trips:
                sid = row.get("stop_id", "")
                if sid:
                    stop_keys.add(f"{agency}::{sid}")

    return stop_keys


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


def _clip_linestring(
    coords: list[tuple[float, float]],
    min_lon: float, max_lon: float, min_lat: float, max_lat: float,
) -> list[tuple[float, float]]:
    """Clip a LineString to a bounding box, interpolating at boundary crossings."""
    def _in_bbox(lon: float, lat: float) -> bool:
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat

    def _intersect(p1: tuple[float, float], p2: tuple[float, float]) -> tuple[float, float]:
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        t = 1.0
        if dx != 0:
            if x2 > max_lon: t = min(t, (max_lon - x1) / dx)
            elif x2 < min_lon: t = min(t, (min_lon - x1) / dx)
        if dy != 0:
            if y2 > max_lat: t = min(t, (max_lat - y1) / dy)
            elif y2 < min_lat: t = min(t, (min_lat - y1) / dy)
        return (x1 + dx * max(0, t), y1 + dy * max(0, t))

    clipped: list[tuple[float, float]] = []
    for i, (lon, lat) in enumerate(coords):
        if _in_bbox(lon, lat):
            if clipped or i == 0:
                clipped.append((lon, lat))
            else:
                edge = _intersect(coords[i - 1], (lon, lat))
                clipped.append(edge)
                clipped.append((lon, lat))
        else:
            if clipped and i > 0 and _in_bbox(*coords[i - 1]):
                edge = _intersect(coords[i - 1], (lon, lat))
                clipped.append(edge)
    return clipped


def build_routes_geojson(
    shapes_df: pl.DataFrame,
    routes_df: pl.DataFrame,
    trips_df: pl.DataFrame,
    clip_bounds: tuple[float, float, float, float] | None = None,
) -> dict:
    """Build GeoJSON FeatureCollection for transit routes."""
    if shapes_df.is_empty() or routes_df.is_empty() or trips_df.is_empty():
        return {"type": "FeatureCollection", "features": []}

    # All shapes for all routes — no picking, no filtering
    all_route_shapes = trips_df.select(["agency", "route_id", "shape_id"]).unique()
    route_shapes = all_route_shapes.join(routes_df, on=["agency", "route_id"], how="inner")

    features: list[dict] = []
    for row in route_shapes.iter_rows(named=True):
        agency = row["agency"]
        shape_id = row["shape_id"]
        route_name = row.get("route_short_name") or row.get("route_long_name") or ""
        route_long = row.get("route_long_name") or ""
        route_type = row.get("route_type", 3)

        # Get shape points sorted by sequence, deduplicated
        # Some feeds (e.g. NJ Transit) reuse sequence numbers for both directions
        shape_points = (
            shapes_df.filter(
                (pl.col("agency") == agency) & (pl.col("shape_id") == shape_id)
            )
            .unique(subset=["sequence"], keep="first")
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

        if clip_bounds:
            min_lat, max_lat, min_lon, max_lon = clip_bounds
            coords = _clip_linestring(coords, min_lon, max_lon, min_lat, max_lat)

        if len(coords) < 2:
            continue

        # Build display name
        display_name = route_name
        if route_long and route_long != route_name:
            display_name = f"{route_name} - {route_long}" if route_name else route_long

        route_type_label = ROUTE_TYPE_LABELS.get(route_type, "other")
        raw_color = row.get("route_color", "")
        color = f"#{raw_color}" if raw_color and not raw_color.startswith("#") else raw_color
        if not color:
            color = "#4A90D9" if route_type in (0, 1, 2) else "#6B7280"

        feature = {
            "type": "Feature",
            "properties": {
                "agency": agency,
                "route_id": row["route_id"],
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

    Only includes stops present in active_stop_keys (matched to rendered routes).
    """
    if stops_df.is_empty():
        return {"type": "FeatureCollection", "features": []}

    features: list[dict] = []
    for row in stops_df.iter_rows(named=True):
        agency = row["agency"]
        stop_id = row["stop_id"]
        key = f"{agency}::{stop_id}"

        if key not in active_stop_keys:
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
    import argparse as ap

    from urbanstack.metro import get_metro

    parser = ap.ArgumentParser(description="Build transit GeoJSON from GTFS feeds")
    parser.add_argument("--metro", default="dfw", help="Metro ID (dfw, chicago, nyc)")
    parser.add_argument("--force", action="store_true", help="Force re-download")
    args = parser.parse_args()

    settings = load_settings()
    settings.ensure_dirs()
    metro = get_metro(args.metro)

    # Step 1: Extract GTFS (uses transit discovery internally)
    logger.info("Extracting GTFS feeds for %s...", metro.metro_id)
    result = extract_gtfs(settings, metro, force=args.force)
    all_routes = result["routes"]
    all_stops = result["stops"]
    all_shapes = result["shapes"]

    if all_routes.is_empty():
        logger.error("No routes extracted. No GeoJSON generated.")
        return 1

    # Get list of agencies that were extracted
    agencies = all_routes["agency"].unique().to_list()
    logger.info("Extracted %d agencies: %s", len(agencies), ", ".join(agencies))

    # Step 2: Load trips.txt for shape->route mapping
    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    trips_df = _load_trips_from_zips(raw_dir, agencies)
    logger.info("Trips: %d unique (agency, route_id, shape_id) rows", len(trips_df))

    # Step 3: Load stop modes
    active_stops, stop_modes = _load_stop_modes(raw_dir, agencies)
    logger.info("Active stop keys: %d", len(active_stops))

    # Clip display to metro bounds (with padding for edge routes).
    # Data stays complete in parquet — only the GeoJSON output is clipped.
    pad = 0.3
    clip = (metro.bounds[0] - pad, metro.bounds[1] + pad, metro.bounds[2] - pad, metro.bounds[3] + pad)

    # Step 4: Build routes GeoJSON — clip LineStrings to metro bounds
    routes_geojson = build_routes_geojson(all_shapes, all_routes, trips_df, clip_bounds=clip)
    route_count = len(routes_geojson["features"])
    logger.info("Routes: %d total", route_count)
    _count_by_agency(routes_geojson["features"], "routes")

    # Step 5: Build stops — only stops that serve rendered routes AND are within metro bounds
    rendered_routes: set[tuple[str, str]] = set()
    for feat in routes_geojson["features"]:
        p = feat["properties"]
        rendered_routes.add((p["agency"], p.get("route_id", "")))

    rendered_stop_keys = _stops_for_routes(raw_dir, agencies, rendered_routes)
    logger.info("Stops matched to rendered routes: %d", len(rendered_stop_keys))

    all_stops = all_stops.filter(
        (pl.col("latitude") >= clip[0]) & (pl.col("latitude") <= clip[1])
        & (pl.col("longitude") >= clip[2]) & (pl.col("longitude") <= clip[3])
    )

    stops_geojson = build_stops_geojson(all_stops, rendered_stop_keys, stop_modes)
    stop_count = len(stops_geojson["features"])
    logger.info("Stops: %d total", stop_count)
    _count_by_agency(stops_geojson["features"], "stops")
    _count_by_mode(stops_geojson["features"])

    # Step 6: Write to metro-specific directory
    out_dir = WEB_DATA_DIR / metro.metro_id
    out_dir.mkdir(parents=True, exist_ok=True)

    routes_path = out_dir / "transit_routes.geojson"
    stops_path = out_dir / "transit_stops.geojson"

    routes_path.write_text(json.dumps(routes_geojson))
    stops_path.write_text(json.dumps(stops_geojson))

    routes_kb = routes_path.stat().st_size / 1024
    stops_kb = stops_path.stat().st_size / 1024

    logger.info("Wrote %s (%.0f KB, %d routes)", routes_path, routes_kb, route_count)
    logger.info("Wrote %s (%.0f KB, %d stops)", stops_path, stops_kb, stop_count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
