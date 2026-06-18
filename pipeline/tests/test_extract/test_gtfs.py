import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.contracts.gtfs import GtfsRoute, GtfsShape, GtfsStop
from urbanstack.extract.gtfs import extract_gtfs


def _make_gtfs_zip(
    routes: str | None = None,
    stops: str | None = None,
    shapes: str | None = None,
) -> bytes:
    if routes is None:
        routes = (
            "route_id,route_short_name,route_long_name,route_type\n"
            "R1,1,Main Street Line,3\n"
            "R2,RED,Red Line,1\n"
        )
    if stops is None:
        stops = (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "S1,Downtown Station,32.7767,-96.7970\n"
            "S2,Uptown Station,32.8000,-96.8000\n"
        )
    if shapes is None:
        shapes = (
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
            "SH1,32.7767,-96.7970,1\n"
            "SH1,32.7800,-96.7950,2\n"
            "SH1,32.7850,-96.7900,3\n"
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("routes.txt", routes)
        zf.writestr("stops.txt", stops)
        zf.writestr("shapes.txt", shapes)
    return buf.getvalue()


def _place_zip(settings: Settings, agency: str = "DART") -> Path:
    raw_dir = settings.raw_dir / "gtfs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / f"{agency.lower().replace(' ', '_')}_gtfs.zip"
    zip_path.write_bytes(_make_gtfs_zip())
    return zip_path


def test_extract_single_agency(settings: Settings) -> None:
    _place_zip(settings, "DART")

    with patch("urbanstack.extract.gtfs.requests.get") as mock_get:
        mock_get.side_effect = AssertionError("Should not download")
        result = extract_gtfs(settings, agencies=["DART"])

    assert "routes" in result
    assert "stops" in result
    assert "shapes" in result
    assert len(result["routes"]) == 2
    assert len(result["stops"]) == 2
    assert len(result["shapes"]) == 3


def test_route_contract(settings: Settings) -> None:
    _place_zip(settings, "DART")

    with patch("urbanstack.extract.gtfs.requests.get"):
        result = extract_gtfs(settings, agencies=["DART"])

    row = result["routes"].to_dicts()[0]
    record = GtfsRoute.model_validate(row)
    assert record.agency == "DART"
    assert record.route_id == "R1"
    assert record.route_type == 3


def test_stop_contract(settings: Settings) -> None:
    _place_zip(settings, "DART")

    with patch("urbanstack.extract.gtfs.requests.get"):
        result = extract_gtfs(settings, agencies=["DART"])

    row = result["stops"].to_dicts()[0]
    record = GtfsStop.model_validate(row)
    assert record.agency == "DART"
    assert record.stop_id == "S1"
    assert record.latitude == pytest.approx(32.7767)
    assert record.longitude == pytest.approx(-96.7970)


def test_shape_contract(settings: Settings) -> None:
    _place_zip(settings, "DART")

    with patch("urbanstack.extract.gtfs.requests.get"):
        result = extract_gtfs(settings, agencies=["DART"])

    row = result["shapes"].to_dicts()[0]
    record = GtfsShape.model_validate(row)
    assert record.agency == "DART"
    assert record.shape_id == "SH1"
    assert record.sequence == 1


def test_idempotent_skip(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "gtfs"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    for name in ("gtfs_routes.parquet", "gtfs_stops.parquet", "gtfs_shapes.parquet"):
        pl.DataFrame({"agency": ["DART"]}).write_parquet(parquet_dir / name)

    with patch("urbanstack.extract.gtfs.requests.get") as mock_get:
        result = extract_gtfs(settings, agencies=["DART"])
        mock_get.assert_not_called()

    assert len(result["routes"]) == 1


def test_force_overwrite(settings: Settings) -> None:
    _place_zip(settings, "DART")
    parquet_dir = settings.staging_dir / "gtfs"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    for name in ("gtfs_routes.parquet", "gtfs_stops.parquet", "gtfs_shapes.parquet"):
        pl.DataFrame({"agency": ["old"]}).write_parquet(parquet_dir / name)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = _make_gtfs_zip()

    with patch("urbanstack.extract.gtfs.requests.get", return_value=mock_resp):
        result = extract_gtfs(settings, agencies=["DART"], force=True)

    assert "old" not in result["routes"]["agency"].to_list()
    assert len(result["routes"]) == 2


def test_download_on_missing_zip(settings: Settings) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = _make_gtfs_zip()

    with patch("urbanstack.extract.gtfs.requests.get", return_value=mock_resp):
        result = extract_gtfs(settings, agencies=["DART"])

    assert len(result["routes"]) == 2
    zip_path = settings.raw_dir / "gtfs" / "dart_gtfs.zip"
    assert zip_path.exists()


def test_unknown_agency_raises(settings: Settings) -> None:
    with pytest.raises(ValueError, match="Unknown agency"):
        extract_gtfs(settings, agencies=["FakeTransit"])


def test_null_lat_lon_skipped(settings: Settings) -> None:
    stops = (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "S1,Good Stop,32.7767,-96.7970\n"
        "S2,Bad Stop,,\n"
        "S3,Zero Stop,0.0,0.0\n"
    )
    raw_dir = settings.raw_dir / "gtfs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "dart_gtfs.zip"
    zip_path.write_bytes(_make_gtfs_zip(stops=stops))

    with patch("urbanstack.extract.gtfs.requests.get"):
        result = extract_gtfs(settings, agencies=["DART"])

    stop_ids = result["stops"]["stop_id"].to_list()
    assert "S1" in stop_ids
    assert "S2" not in stop_ids
    assert "S3" not in stop_ids


def test_parquets_saved(settings: Settings) -> None:
    _place_zip(settings, "DART")

    with patch("urbanstack.extract.gtfs.requests.get"):
        extract_gtfs(settings, agencies=["DART"])

    for name in ("gtfs_routes.parquet", "gtfs_stops.parquet", "gtfs_shapes.parquet"):
        assert (settings.staging_dir / "gtfs" / name).exists()


def test_multiple_agencies(settings: Settings) -> None:
    _place_zip(settings, "DART")
    raw_dir = settings.raw_dir / "gtfs"
    zip_path = raw_dir / "trinity_metro_gtfs.zip"
    routes = (
        "route_id,route_short_name,route_long_name,route_type\n"
        "TM1,5,Fifth Ave,3\n"
    )
    zip_path.write_bytes(_make_gtfs_zip(routes=routes))

    with patch("urbanstack.extract.gtfs.requests.get"):
        result = extract_gtfs(settings, agencies=["DART", "Trinity Metro"])

    agencies = result["routes"]["agency"].unique().to_list()
    assert "DART" in agencies
    assert "Trinity Metro" in agencies
    assert len(result["routes"]) == 3
