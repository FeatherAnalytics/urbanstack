import json
import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


def load_boundaries(geojson_path: Path) -> list[tuple[str, list[list[list[float]]]]]:
    """Load GeoJSON features as (id, rings) pairs.

    Handles both Polygon and MultiPolygon geometry types.
    Each entry's rings is a list of linear rings (outer + holes).
    """
    with open(geojson_path) as f:
        geo = json.load(f)

    boundaries: list[tuple[str, list[list[list[float]]]]] = []
    for feat in geo["features"]:
        area_id = str(feat["properties"]["GEOID"])
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            rings = geom["coordinates"]
        elif geom["type"] == "MultiPolygon":
            rings = [ring for poly in geom["coordinates"] for ring in poly]
        else:
            continue
        boundaries.append((area_id, rings))
    return boundaries


def point_in_polygon(lat: float, lon: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test. Coordinates are [lon, lat] in the ring."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def _point_in_area(
    lat: float,
    lon: float,
    rings: list[list[list[float]]],
) -> bool:
    """Check if a point falls within any ring of an area."""
    for ring in rings:
        if point_in_polygon(lat, lon, ring):
            return True
    return False


def assign_points_to_areas(
    points: pl.DataFrame,
    boundaries: list[tuple[str, list[list[list[float]]]]],
    *,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
) -> pl.DataFrame:
    """Assign each point to an area via point-in-polygon. Adds 'area_id' column.

    Points with null lat/lon or that don't fall in any area get area_id=None.
    """
    lats = points[lat_col].to_list()
    lons = points[lon_col].to_list()

    area_ids: list[str | None] = []
    for lat, lon in zip(lats, lons):
        if lat is None or lon is None:
            area_ids.append(None)
            continue
        matched: str | None = None
        for area_id, rings in boundaries:
            if _point_in_area(lat, lon, rings):
                matched = area_id
                break
        area_ids.append(matched)

    assigned = sum(1 for a in area_ids if a is not None)
    logger.info(
        "Spatial join: %d/%d points assigned to areas", assigned, len(area_ids)
    )

    return points.with_columns(pl.Series("area_id", area_ids, dtype=pl.Utf8))
