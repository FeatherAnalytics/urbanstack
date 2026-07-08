"""Tests for metro data completeness validation."""

from pathlib import Path

from urbanstack.validate import FileCheck, MetroReport, check_file, check_parquet


def test_check_file_exists(tmp_path: Path) -> None:
    f = tmp_path / "test.geojson"
    f.write_text('{"type": "FeatureCollection", "features": []}')
    result = check_file(f)
    assert result.exists is True
    assert result.size_bytes > 0


def test_check_file_missing(tmp_path: Path) -> None:
    result = check_file(tmp_path / "missing.geojson")
    assert result.exists is False


def test_check_parquet_missing(tmp_path: Path) -> None:
    result = check_parquet(tmp_path / "missing.parquet")
    assert result.exists is False
    assert result.row_count == 0


def test_metro_report_has_warnings() -> None:
    report = MetroReport(metro_id="test", metro_name="Test MSA")
    report.add_warning("UMR data missing")
    assert len(report.warnings) == 1
    assert report.ok is True  # warnings don't fail


def test_metro_report_has_errors() -> None:
    report = MetroReport(metro_id="test", metro_name="Test MSA")
    report.add_error("County mart missing")
    assert len(report.errors) == 1
    assert report.ok is False  # errors fail
