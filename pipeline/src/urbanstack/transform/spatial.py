import json
import logging
import math
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

# Each area has a list of polygons; each polygon is [outer_ring, hole1, hole2, ...]
Boundaries = list[tuple[str, list[list[list[list[float]]]]]]


def load_boundaries(geojson_path: Path) -> Boundaries:
    """Load GeoJSON features as (id, polygons) pairs.

    Each polygon is a list of rings: [outer_ring, hole1, hole2, ...].
    Polygon geometries produce one polygon; MultiPolygon produces multiple.
    """
    with open(geojson_path) as f:
        geo = json.load(f)

    boundaries: Boundaries = []
    for feat in geo["features"]:
        area_id = str(feat["properties"]["GEOID"])
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            polygons = [geom["coordinates"]]
        elif geom["type"] == "MultiPolygon":
            polygons = geom["coordinates"]
        else:
            continue
        boundaries.append((area_id, polygons))
    return boundaries


def compute_bbox(boundaries: Boundaries) -> tuple[float, float, float, float]:
    """Compute (south, west, north, east) bounding box from loaded boundaries."""
    min_lat = min_lon = float("inf")
    max_lat = max_lon = float("-inf")
    found = False
    for _area_id, polygons in boundaries:
        for polygon_rings in polygons:
            for ring in polygon_rings:
                for lon, lat in ring:
                    min_lat, max_lat = min(min_lat, lat), max(max_lat, lat)
                    min_lon, max_lon = min(min_lon, lon), max(max_lon, lon)
                    found = True
    if not found:
        raise ValueError("No coordinates found in boundaries")
    return (min_lat, min_lon, max_lat, max_lon)


def polygon_area_sqm(ring: list[list[float]]) -> float:
    """Approximate polygon area in sq meters via shoelace on equirectangular projection."""
    if len(ring) < 3:
        return 0.0
    mid_lat = sum(c[1] for c in ring) / len(ring)
    lon_m = 111_320.0 * math.cos(math.radians(mid_lat))
    area = 0.0
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        x_i, y_i = ring[i][0] * lon_m, ring[i][1] * 111_320.0
        x_j, y_j = ring[j][0] * lon_m, ring[j][1] * 111_320.0
        area += x_i * y_j - x_j * y_i
    return abs(area) / 2.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two lat/lon points."""
    r = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_centroids(boundaries: Boundaries) -> pl.DataFrame:
    # yagni: vertex-mean centroid, use area-weighted if placement errors appear
    """Compute centroid (lat, lon) for each boundary from first polygon's outer ring."""
    rows: list[dict[str, object]] = []
    for area_id, polygons in boundaries:
        if not polygons or not polygons[0] or not polygons[0][0]:
            continue
        outer = polygons[0][0]
        lat = sum(c[1] for c in outer) / len(outer)
        lon = sum(c[0] for c in outer) / len(outer)
        rows.append({"area_id": area_id, "centroid_lat": lat, "centroid_lon": lon})
    return pl.DataFrame(rows)


def compute_amenity_proximity(
    centroids: pl.DataFrame,
    amenities: pl.DataFrame,
    *,
    prefix: str = "park",
    radius_m: float = 400.0,
) -> pl.DataFrame:
    """Count amenities within radius of each centroid and sum their area.

    Returns DataFrame with area_id, {prefix}_count_nearby, total_{prefix}_area_sqm.
    """
    # yagni: brute-force with bbox prefilter, use R-tree when areas > 50k
    area_ids = centroids["area_id"].to_list()
    area_lats = centroids["centroid_lat"].to_list()
    area_lons = centroids["centroid_lon"].to_list()

    am_lats = amenities["centroid_lat"].to_list()
    am_lons = amenities["centroid_lon"].to_list()
    am_areas = amenities["area_sqm"].to_list()

    dlat = radius_m / 111_320.0

    counts: list[int] = []
    total_areas: list[float] = []

    for a_lat, a_lon in zip(area_lats, area_lons, strict=True):
        dlon = radius_m / (111_320.0 * max(math.cos(math.radians(a_lat)), 1e-10))
        count = 0
        area_sum = 0.0
        for p_lat, p_lon, p_area in zip(am_lats, am_lons, am_areas, strict=True):
            if abs(a_lat - p_lat) > dlat or abs(a_lon - p_lon) > dlon:
                continue
            if haversine_m(a_lat, a_lon, p_lat, p_lon) <= radius_m:
                count += 1
                area_sum += p_area
        counts.append(count)
        total_areas.append(area_sum)

    return pl.DataFrame({
        "area_id": area_ids,
        f"{prefix}_count_nearby": counts,
        f"total_{prefix}_area_sqm": total_areas,
    })


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
    polygons: list[list[list[list[float]]]],
) -> bool:
    """Check if point is inside any polygon (outer ring minus holes)."""
    for polygon_rings in polygons:
        if not polygon_rings:
            continue
        if not point_in_polygon(lat, lon, polygon_rings[0]):
            continue
        if not any(point_in_polygon(lat, lon, hole) for hole in polygon_rings[1:]):
            return True
    return False


def assign_points_to_areas(
    points: pl.DataFrame,
    boundaries: Boundaries,
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
    for lat, lon in zip(lats, lons, strict=True):
        if lat is None or lon is None:
            area_ids.append(None)
            continue
        matched: str | None = None
        for area_id, polygons in boundaries:
            if _point_in_area(lat, lon, polygons):
                matched = area_id
                break
        area_ids.append(matched)

    assigned = sum(1 for a in area_ids if a is not None)
    logger.info(
        "Spatial join: %d/%d points assigned to areas", assigned, len(area_ids)
    )

    return points.with_columns(pl.Series("area_id", area_ids, dtype=pl.Utf8))
