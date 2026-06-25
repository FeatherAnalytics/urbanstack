import json
from pathlib import Path

import polars as pl
import pytest

from urbanstack.transform.spatial import (
    _point_in_area,
    compute_bbox,
    compute_centroids,
    compute_amenity_proximity,
    haversine_m,
    load_boundaries,
    point_in_polygon,
    polygon_area_sqm,
)

MOCK_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-97.0, 32.5],
                    [-96.0, 32.5],
                    [-96.0, 33.0],
                    [-97.0, 33.0],
                    [-97.0, 32.5],
                ]],
            },
            "properties": {"GEOID": "48113"},
        },
    ],
}

MOCK_MULTIPOLYGON_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[-97, 32], [-96, 32], [-96, 33], [-97, 33], [-97, 32]]],
                    [[[-95, 34], [-94, 34], [-94, 35], [-95, 35], [-95, 34]]],
                ],
            },
            "properties": {"GEOID": "48999"},
        },
    ],
}


def _write_geojson(path: Path, data: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data or MOCK_GEOJSON, f)


def test_compute_bbox(tmp_path: Path) -> None:
    gj_path = tmp_path / "test.geojson"
    _write_geojson(gj_path)

    boundaries = load_boundaries(gj_path)
    south, west, north, east = compute_bbox(boundaries)
    assert south == 32.5
    assert west == -97.0
    assert north == 33.0
    assert east == -96.0


def test_compute_bbox_empty() -> None:
    with pytest.raises(ValueError, match="No coordinates"):
        compute_bbox([])


def test_polygon_area_sqm_rectangle() -> None:
    coords = [
        [-96.803, 32.788],
        [-96.801, 32.788],
        [-96.801, 32.790],
        [-96.803, 32.790],
        [-96.803, 32.788],
    ]
    area = polygon_area_sqm(coords)
    assert area > 0
    assert 30_000 < area < 70_000


def test_polygon_area_sqm_empty() -> None:
    assert polygon_area_sqm([]) == 0.0
    assert polygon_area_sqm([[0, 0]]) == 0.0


def test_point_in_polygon_inside() -> None:
    ring = [[-97, 32], [-96, 32], [-96, 33], [-97, 33], [-97, 32]]
    assert point_in_polygon(32.5, -96.5, ring) is True


def test_point_in_polygon_outside() -> None:
    ring = [[-97, 32], [-96, 32], [-96, 33], [-97, 33], [-97, 32]]
    assert point_in_polygon(34.0, -96.5, ring) is False


def test_point_in_area_respects_holes() -> None:
    outer = [[-97, 32], [-96, 32], [-96, 33], [-97, 33], [-97, 32]]
    hole = [[-96.7, 32.3], [-96.3, 32.3], [-96.3, 32.7], [-96.7, 32.7], [-96.7, 32.3]]
    polygons = [[outer, hole]]

    assert _point_in_area(32.5, -96.5, polygons) is False, "inside hole"
    assert _point_in_area(32.1, -96.5, polygons) is True, "in outer, outside hole"
    assert _point_in_area(34.0, -96.5, polygons) is False, "outside outer"


def test_point_in_area_multipolygon() -> None:
    poly1 = [[[-97, 32], [-96, 32], [-96, 33], [-97, 33], [-97, 32]]]
    poly2 = [[[-95, 34], [-94, 34], [-94, 35], [-95, 35], [-95, 34]]]
    polygons = [poly1, poly2]

    assert _point_in_area(32.5, -96.5, polygons) is True, "inside poly1"
    assert _point_in_area(34.5, -94.5, polygons) is True, "inside poly2"
    assert _point_in_area(33.5, -95.5, polygons) is False, "between polys"


def test_point_in_area_no_holes() -> None:
    outer = [[-97, 32], [-96, 32], [-96, 33], [-97, 33], [-97, 32]]
    assert _point_in_area(32.5, -96.5, [[outer]]) is True


def test_point_in_area_empty() -> None:
    assert _point_in_area(32.5, -96.5, []) is False


def test_load_boundaries_multipolygon(tmp_path: Path) -> None:
    gj_path = tmp_path / "multi.geojson"
    _write_geojson(gj_path, MOCK_MULTIPOLYGON_GEOJSON)

    boundaries = load_boundaries(gj_path)
    assert len(boundaries) == 1
    area_id, polygons = boundaries[0]
    assert area_id == "48999"
    assert len(polygons) == 2


def test_haversine_same_point() -> None:
    assert haversine_m(32.78, -96.80, 32.78, -96.80) == 0.0


def test_haversine_known_distance() -> None:
    d = haversine_m(32.78, -96.80, 32.79, -96.80)
    assert 1100 < d < 1200


def test_compute_centroids(tmp_path: Path) -> None:
    gj_path = tmp_path / "test.geojson"
    _write_geojson(gj_path)
    boundaries = load_boundaries(gj_path)
    centroids = compute_centroids(boundaries)
    assert len(centroids) == 1
    assert "area_id" in centroids.columns
    row = centroids.row(0, named=True)
    assert 32.0 < row["centroid_lat"] < 34.0
    assert -98.0 < row["centroid_lon"] < -95.0


def test_compute_amenity_proximity_within_radius() -> None:
    centroids = pl.DataFrame({
        "area_id": ["A", "B"],
        "centroid_lat": [32.789, 33.500],
        "centroid_lon": [-96.802, -97.000],
    })
    parks = pl.DataFrame({
        "centroid_lat": [32.790, 32.791],
        "centroid_lon": [-96.801, -96.803],
        "area_sqm": [5000.0, 3000.0],
    })
    result = compute_amenity_proximity(centroids, parks, radius_m=400)
    rows = result.sort("area_id").to_dicts()
    assert rows[0]["park_count_nearby"] == 2
    assert rows[0]["total_park_area_sqm"] == 8000.0
    assert rows[1]["park_count_nearby"] == 0
    assert rows[1]["total_park_area_sqm"] == 0.0


def test_compute_amenity_proximity_empty_parks() -> None:
    centroids = pl.DataFrame({
        "area_id": ["A"],
        "centroid_lat": [32.789],
        "centroid_lon": [-96.802],
    })
    parks = pl.DataFrame({
        "centroid_lat": pl.Series([], dtype=pl.Float64),
        "centroid_lon": pl.Series([], dtype=pl.Float64),
        "area_sqm": pl.Series([], dtype=pl.Float64),
    })
    result = compute_amenity_proximity(centroids, parks)
    assert result["park_count_nearby"][0] == 0
