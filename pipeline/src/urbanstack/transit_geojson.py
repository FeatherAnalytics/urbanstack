"""Build transit route/stop GeoJSON from GTFS feeds."""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from urbanstack.config import Settings
    from urbanstack.metro import MetroConfig

logger = logging.getLogger("urbanstack.transit_geojson")


def _feature_vertices(geometry: dict) -> list[list[float]]:
    if geometry["type"] == "LineString":
        return geometry["coordinates"]
    if geometry["type"] == "MultiLineString":
        return [c for part in geometry["coordinates"] for c in part]
    return []


def _keep_servicing_routes(
    features: list[dict],
    settings: Settings,
    metro: MetroConfig,
) -> list[dict]:
    """Drop routes that never enter the metro's counties.

    Clipping is rectangular, and in dense corridors that rectangle reaches well past
    the MSA — a Philadelphia box spans Allentown, Reading, Lancaster, and north Jersey.
    Operators with no service inside the counties would otherwise dominate the map.
    """
    from urbanstack.transform.spatial import (
        load_boundaries,
        point_in_bounded_areas,
        prepare_bounded_areas,
    )

    counties_path = settings.web_data_dir(metro.metro_id) / "counties.geojson"
    if not counties_path.exists():
        logger.warning(
            "No county boundaries for %s — keeping all routes inside the clip box",
            metro.metro_id,
        )
        return features

    areas = prepare_bounded_areas(load_boundaries(counties_path))
    kept: list[dict] = []
    dropped_by_agency: dict[str, int] = {}

    for feat in features:
        # Every vertex is tested, not a sample — a route may clip the MSA for only a
        # point or two, and sampling would discard real service. The bbox prefilter
        # keeps the common all-outside case cheap, and the scan exits on first hit.
        servicing = any(
            point_in_bounded_areas(v[1], v[0], areas)
            for v in _feature_vertices(feat["geometry"])
        )
        if servicing:
            kept.append(feat)
        else:
            agency = feat["properties"].get("agency", "unknown")
            dropped_by_agency[agency] = dropped_by_agency.get(agency, 0) + 1

    if dropped_by_agency:
        total = sum(dropped_by_agency.values())
        worst = sorted(dropped_by_agency.items(), key=lambda kv: -kv[1])[:5]
        logger.info(
            "%s: dropped %d of %d route shapes with no service in the MSA (%s)",
            metro.metro_id,
            total,
            len(features),
            ", ".join(f"{a}={n}" for a, n in worst),
        )
    return kept


def build_transit_geojson(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Build transit GeoJSON for a metro. Returns counts dict."""
    web_dir = settings.web_data_dir(metro.metro_id)
    routes_gz = web_dir / "transit_routes.geojson.gz"
    stops_gz = web_dir / "transit_stops.geojson.gz"

    if routes_gz.exists() and stops_gz.exists() and not force:
        logger.info("Transit GeoJSON exists, skipping: %s", web_dir)
        return {"routes": 0, "stops": 0, "skipped": True}

    import sys

    # yagni: import from scripts/, move functions into this module when script is retired
    scripts_dir = str(Path(__file__).resolve().parent.parent.parent / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from build_transit_geojson import (
        _load_stop_modes,
        _load_trips_from_zips,
        _stops_for_routes,
        build_routes_geojson,
        build_stops_geojson,
    )

    from urbanstack.extract.gtfs import extract_gtfs

    result = extract_gtfs(settings, metro, force=force)
    all_routes = result["routes"]
    all_stops = result["stops"]
    all_shapes = result["shapes"]

    if all_routes.is_empty():
        logger.warning("No GTFS routes for %s — writing empty transit GeoJSON", metro.metro_id)
        empty = {"type": "FeatureCollection", "features": []}
        web_dir.mkdir(parents=True, exist_ok=True)
        for path in (web_dir / "transit_routes.geojson", web_dir / "transit_stops.geojson"):
            path.write_text(json.dumps(empty))
            gz_path = Path(str(path) + ".gz")
            gz_path.write_bytes(gzip.compress(path.read_bytes()))
        return {"routes": 0, "stops": 0}

    agencies = all_routes["agency"].unique().to_list()
    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    trips_df = _load_trips_from_zips(raw_dir, agencies)

    active_stops, stop_modes = _load_stop_modes(raw_dir, agencies)

    pad = 0.3
    clip = (metro.bounds[0] - pad, metro.bounds[1] + pad, metro.bounds[2] - pad, metro.bounds[3] + pad)

    routes_geojson = build_routes_geojson(all_shapes, all_routes, trips_df, clip_bounds=clip)
    routes_geojson["features"] = _keep_servicing_routes(
        routes_geojson["features"], settings, metro
    )
    route_count = len(routes_geojson["features"])

    rendered_routes: set[tuple[str, str]] = set()
    for feat in routes_geojson["features"]:
        p = feat["properties"]
        rendered_routes.add((p["agency"], p.get("route_id", "")))

    import polars as pl

    rendered_stop_keys = _stops_for_routes(raw_dir, agencies, rendered_routes) if rendered_routes else set()
    all_stops = all_stops.filter(
        (pl.col("latitude") >= clip[0])
        & (pl.col("latitude") <= clip[1])
        & (pl.col("longitude") >= clip[2])
        & (pl.col("longitude") <= clip[3])
    )
    stops_geojson = build_stops_geojson(all_stops, rendered_stop_keys, stop_modes)
    stop_count = len(stops_geojson["features"])

    web_dir.mkdir(parents=True, exist_ok=True)
    for name, geojson in [("transit_routes", routes_geojson), ("transit_stops", stops_geojson)]:
        path = web_dir / f"{name}.geojson"
        path.write_text(json.dumps(geojson))
        gz_path = Path(str(path) + ".gz")
        gz_path.write_bytes(gzip.compress(path.read_bytes()))
        logger.info("Wrote %s (%.0f KB)", gz_path, gz_path.stat().st_size / 1024)

    return {"routes": route_count, "stops": stop_count}
