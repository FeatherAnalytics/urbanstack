from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.contracts.umr import UmrRecord
from urbanstack.extract.umr import extract_umr
from urbanstack.metro import MetroConfig


def _make_csv_content() -> str:
    lines = [
        '"Urban Area","Year","Travel Time Index","Planning Time Index",'
        '"Annual Delay per Auto Commuter (hours)",'
        '"Congestion Cost per Auto Commuter (dollars)",'
        '"Total Delay (1,000 person-hours)",'
        '"Total Excess Fuel Consumed (1,000 gallons)"',
        '"Dallas-Fort Worth-Arlington","2020","1.22","1.90","47","1034","188640","78500"',
        '"Dallas-Fort Worth-Arlington","2021","1.20","1.85","42","950","170000","71000"',
        '"Dallas-Fort Worth-Arlington","2022","1.25","1.95","52","1100","200000","83000"',
        '"Houston","2020","1.30","2.10","60","1200","250000","100000"',
    ]
    return "\n".join(lines)


def _write_csv(settings: Settings) -> Path:
    raw_dir = settings.raw_dir / "umr"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = raw_dir / "umr_data.csv"
    csv_path.write_text(_make_csv_content())
    return csv_path


def test_extract_from_local_csv(settings: Settings, metro: MetroConfig) -> None:
    _write_csv(settings)

    with patch("urbanstack.extract.umr._try_download", return_value=None):
        df = extract_umr(settings, metro)

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 3
    assert "urban_area" in df.columns
    assert "year" in df.columns
    assert "travel_time_index" in df.columns
    assert all(
        a.lower().startswith("dallas")
        for a in df["urban_area"].to_list()
    )


def test_filters_out_non_dfw(settings: Settings, metro: MetroConfig) -> None:
    _write_csv(settings)

    with patch("urbanstack.extract.umr._try_download", return_value=None):
        df = extract_umr(settings, metro)

    areas = df["urban_area"].to_list()
    assert "Houston" not in [a.strip() for a in areas]


def test_contract_validation(settings: Settings, metro: MetroConfig) -> None:
    _write_csv(settings)

    with patch("urbanstack.extract.umr._try_download", return_value=None):
        df = extract_umr(settings, metro)

    row_dict = df.to_dicts()[0]
    record = UmrRecord.model_validate(row_dict)
    assert record.urban_area == "Dallas-Fort Worth-Arlington"
    assert record.year == 2020
    assert record.travel_time_index == 1.22


def test_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "umr"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"umr_{metro.metro_id}.parquet"
    existing = pl.DataFrame({
        "urban_area": ["Dallas-Fort Worth-Arlington"],
        "year": [2020],
    })
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.umr._try_download") as mock_dl:
        df = extract_umr(settings, metro)
        mock_dl.assert_not_called()

    assert len(df) == 1


def test_force_overwrite(settings: Settings, metro: MetroConfig) -> None:
    _write_csv(settings)
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "umr"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"umr_{metro.metro_id}.parquet"
    existing = pl.DataFrame({"urban_area": ["old"], "year": [1999]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.umr._try_download", return_value=None):
        df = extract_umr(settings, metro, force=True)

    assert "old" not in df["urban_area"].to_list()
    assert len(df) == 3


def test_no_file_raises(settings: Settings, metro: MetroConfig) -> None:
    with (
        patch("urbanstack.extract.umr._try_download", return_value=None),
        pytest.raises(FileNotFoundError, match="No UMR data found"),
    ):
        extract_umr(settings, metro)


def test_parquet_saved(settings: Settings, metro: MetroConfig) -> None:
    _write_csv(settings)

    with patch("urbanstack.extract.umr._try_download", return_value=None):
        extract_umr(settings, metro)

    parquet_path = settings.metro_staging_dir(metro.metro_id) / "umr" / f"umr_{metro.metro_id}.parquet"
    assert parquet_path.exists()


def test_download_saves_raw(settings: Settings) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = b"fake xlsx content"

    with patch("urbanstack.extract.umr.requests.get", return_value=mock_resp):
        from urbanstack.extract.umr import _try_download

        result = _try_download(settings)

    assert result is not None
    assert result.exists()
    assert result.name == "complete-data-umr.xlsx"


def test_metric_values(settings: Settings, metro: MetroConfig) -> None:
    _write_csv(settings)

    with patch("urbanstack.extract.umr._try_download", return_value=None):
        df = extract_umr(settings, metro)

    row_2020 = df.filter(pl.col("year") == 2020).to_dicts()[0]
    assert row_2020["annual_delay_per_commuter"] == 47.0
    assert row_2020["congestion_cost_per_commuter"] == 1034.0
    assert row_2020["total_delay_thousand_hours"] == 188640.0
