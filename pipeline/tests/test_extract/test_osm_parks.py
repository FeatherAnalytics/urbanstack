import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.contracts.osm_parks import OsmParkRecord
from urbanstack.extract.osm_parks import (
    _bbox_area_sqm,
    _build_overpass_query,
    _dedup_parks,
    _parse_element,
    extract_osm_parks,
)
from urbanstack.metro import MetroConfig

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

MOCK_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "way",
            "id": 12345,
            "tags": {"leisure": "park", "name": "Klyde Warren Park"},
            "center": {"lat": 32.789, "lon": -96.802},
            "bounds": {
                "minlat": 32.788, "minlon": -96.803,
                "maxlat": 32.790, "maxlon": -96.801,
            },
        },
        {
            "type": "way",
            "id": 67890,
            "tags": {"leisure": "playground", "name": "Oak Lawn Playground"},
            "center": {"lat": 32.810, "lon": -96.820},
            "bounds": {
                "minlat": 32.809, "minlon": -96.821,
                "maxlat": 32.811, "maxlon": -96.819,
            },
        },
        {
            "type": "way",
            "id": 99999,
            "tags": {"building": "yes"},
            "center": {"lat": 32.800, "lon": -96.800},
        },
    ],
}


def _write_mock_geojson(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(MOCK_GEOJSON, f)


@pytest.fixture()
def mock_geojson_dir(settings: Settings, metro: MetroConfig) -> Path:
    d = settings.web_data_dir(metro.metro_id)
    d.mkdir(parents=True, exist_ok=True)
    _write_mock_geojson(d / "counties.geojson")
    return d


def test_build_overpass_query() -> None:
    query = _build_overpass_query((32.0, -97.0, 33.0, -96.0))
    assert "32.0,-97.0,33.0,-96.0" in query
    assert '"leisure"="park"' in query
    assert '"leisure"="playground"' in query
    assert '"landuse"="recreation_ground"' in query
    assert "out bb qt" in query


def test_bbox_area_sqm() -> None:
    bounds = {"minlat": 32.788, "minlon": -96.803, "maxlat": 32.790, "maxlon": -96.801}
    area = _bbox_area_sqm(bounds)
    assert area > 0
    assert 30_000 < area < 70_000


def test_parse_element_park() -> None:
    el = MOCK_OVERPASS_RESPONSE["elements"][0]
    result = _parse_element(el)
    assert result is not None
    assert result["osm_id"] == 12345
    assert result["name"] == "Klyde Warren Park"
    assert result["park_type"] == "park"
    assert result["centroid_lat"] == 32.789
    assert result["centroid_lon"] == -96.802
    assert result["area_sqm"] > 0


def test_parse_element_playground() -> None:
    el = MOCK_OVERPASS_RESPONSE["elements"][1]
    result = _parse_element(el)
    assert result is not None
    assert result["park_type"] == "playground"
    assert result["area_sqm"] > 0


def test_parse_element_non_park() -> None:
    assert _parse_element(MOCK_OVERPASS_RESPONSE["elements"][2]) is None


def test_parse_element_no_center_no_bounds() -> None:
    el = {"id": 1, "tags": {"leisure": "park"}}
    assert _parse_element(el) is None


def test_parse_element_partial_bounds_rejected() -> None:
    el = {"id": 1, "tags": {"leisure": "park"}, "bounds": {"minlat": 32.5}}
    assert _parse_element(el) is None


def test_parse_element_fallback_to_bounds_centroid() -> None:
    el = {
        "id": 1,
        "tags": {"leisure": "park"},
        "bounds": {"minlat": 32.0, "maxlat": 33.0, "minlon": -97.0, "maxlon": -96.0},
    }
    result = _parse_element(el)
    assert result is not None
    assert result["centroid_lat"] == 32.5
    assert result["centroid_lon"] == -96.5


def test_dedup_keeps_largest_area() -> None:
    records = [
        {"osm_id": 1, "name": "Park A (way)", "park_type": "park",
         "area_sqm": 0, "centroid_lat": 32.78900, "centroid_lon": -96.80200},
        {"osm_id": 2, "name": "Park A (relation)", "park_type": "park",
         "area_sqm": 5000, "centroid_lat": 32.78901, "centroid_lon": -96.80201},
    ]
    deduped = _dedup_parks(records)
    assert len(deduped) == 1
    assert deduped[0]["area_sqm"] == 5000


def test_dedup_keeps_different_types() -> None:
    records = [
        {"osm_id": 1, "name": "A", "park_type": "park",
         "area_sqm": 100, "centroid_lat": 32.789, "centroid_lon": -96.802},
        {"osm_id": 2, "name": "B", "park_type": "playground",
         "area_sqm": 50, "centroid_lat": 32.789, "centroid_lon": -96.802},
    ]
    deduped = _dedup_parks(records)
    assert len(deduped) == 2


def test_contract_validation() -> None:
    parsed = _parse_element(MOCK_OVERPASS_RESPONSE["elements"][0])
    record = OsmParkRecord.model_validate(parsed)
    assert record.osm_id == 12345
    assert record.park_type == "park"


def test_extract_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "osm_parks"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"osm_parks_{metro.metro_id}.parquet"
    existing = pl.DataFrame({
        "osm_id": [1], "name": ["Test"], "park_type": ["park"],
        "area_sqm": [100.0], "centroid_lat": [32.0], "centroid_lon": [-96.0],
    })
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.osm_parks._fetch_parks") as mock_fetch:
        df = extract_osm_parks(settings, metro)
        mock_fetch.assert_not_called()

    assert len(df) == 1


def test_extract_full_flow(
    settings: Settings, metro: MetroConfig, mock_geojson_dir: Path,
) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = MOCK_OVERPASS_RESPONSE

    with patch("urbanstack.extract.osm_parks._overpass_session") as mock_session:
        mock_session.return_value.post.return_value = mock_resp
        df = extract_osm_parks(settings, metro, force=True)

    assert len(df) == 2
    assert set(df["park_type"].to_list()) == {"park", "playground"}

    staging = settings.metro_staging_dir(metro.metro_id)
    parquet_path = staging / "osm_parks" / f"osm_parks_{metro.metro_id}.parquet"
    assert parquet_path.exists()


def test_extract_uses_validated_model_dump(
    settings: Settings, metro: MetroConfig, mock_geojson_dir: Path,
) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = MOCK_OVERPASS_RESPONSE

    with patch("urbanstack.extract.osm_parks._overpass_session") as mock_session:
        mock_session.return_value.post.return_value = mock_resp
        df = extract_osm_parks(settings, metro, force=True)

    assert df["osm_id"].dtype == pl.Int64
    assert df["area_sqm"].dtype == pl.Float64


def test_extract_empty_response(
    settings: Settings, metro: MetroConfig, mock_geojson_dir: Path,
) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"elements": []}

    with patch("urbanstack.extract.osm_parks._overpass_session") as mock_session:
        mock_session.return_value.post.return_value = mock_resp
        df = extract_osm_parks(settings, metro, force=True)

    assert len(df) == 0
    assert "osm_id" in df.columns
