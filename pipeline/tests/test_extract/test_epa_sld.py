import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl

from urbanstack.config import Settings
from urbanstack.contracts.epa_sld import EpaSldRecord
from urbanstack.extract.epa_sld import extract_epa_sld
from urbanstack.metro import MetroConfig

CSV_HEADER = [
    "GEOID10",
    "STATEFP",
    "COUNTYFP",
    "TRACTCE",
    "CBSA",
    "D1A",
    "D1B",
    "D1C",
    "D2A_JPHH",
    "D2B_E8MIXA",
    "D3B",
    "D5DR",
    "D5DE",
    "D4A",
    "D4D",
    "NatWalkInd",
    "Pct_AO0",
    "AutoOwn",
]

DALLAS_ROW = [
    "481130191001",
    "48",
    "113",
    "019100",
    "19100",
    "5.2",
    "12.3",
    "8.1",
    "1.5",
    "0.82",
    "120.5",
    "0.45",
    "0.67",
    "300",
    "50",
    "14.5",
    "0.12",
    "1.8",
]

COLLIN_ROW = [
    "480850302001",
    "48",
    "085",
    "030200",
    "19100",
    "3.1",
    "8.0",
    "4.5",
    "1.2",
    "0.65",
    "80.0",
    "0.30",
    "0.40",
    "500",
    "20",
    "10.2",
    "0.05",
    "2.1",
]

HOUSTON_ROW = [
    "482010401001",
    "48",
    "201",
    "040100",
    "26420",
    "6.0",
    "15.0",
    "10.0",
    "2.0",
    "0.90",
    "150.0",
    "0.50",
    "0.70",
    "200",
    "60",
    "16.0",
    "0.15",
    "1.5",
]

CA_ROW = [
    "060370101001",
    "06",
    "037",
    "010100",
    "31080",
    "10.0",
    "20.0",
    "15.0",
    "3.0",
    "0.95",
    "200.0",
    "0.80",
    "0.90",
    "100",
    "80",
    "18.0",
    "0.20",
    "1.2",
]

TARRANT_ROW = [
    "484390101001",
    "48",
    "439",
    "010100",
    "19100",
    "4.0",
    "10.0",
    "6.0",
    "1.3",
    "0.70",
    "100.0",
    "0.35",
    "0.50",
    "400",
    "30",
    "12.0",
    "0.08",
    "1.9",
]


def _write_mock_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for row in [DALLAS_ROW, COLLIN_ROW, HOUSTON_ROW, CA_ROW, TARRANT_ROW]:
            writer.writerow(row)


def test_filters_to_dfw_only(settings: Settings, metro: MetroConfig) -> None:
    csv_path = settings.raw_dir / "epa_sld" / "sld_v3.csv"
    _write_mock_csv(csv_path)

    with patch("urbanstack.extract.epa_sld._download_csv"):
        df = extract_epa_sld(settings, metro, force=True)

    assert len(df) == 3
    assert set(df["county_fips"].to_list()) == {"113", "085", "439"}
    assert "201" not in df["county_fips"].to_list()
    assert "037" not in df["county_fips"].to_list()


def test_contract_validation(settings: Settings, metro: MetroConfig) -> None:
    csv_path = settings.raw_dir / "epa_sld" / "sld_v3.csv"
    _write_mock_csv(csv_path)

    with patch("urbanstack.extract.epa_sld._download_csv"):
        df = extract_epa_sld(settings, metro, force=True)

    row = df.filter(pl.col("county_fips") == "113").to_dicts()[0]
    record = EpaSldRecord.model_validate(row)
    assert record.geoid == "481130191001"
    assert record.nat_walk_ind == 14.5
    assert record.d1a == 5.2


def test_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "epa_sld"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"epa_sld_{metro.metro_id}.parquet"
    existing = pl.DataFrame({"geoid": ["481130191001"], "state_fips": ["48"]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.epa_sld._download_csv") as mock_dl:
        df = extract_epa_sld(settings, metro)
        mock_dl.assert_not_called()

    assert len(df) == 1


def test_download_called_when_no_csv(settings: Settings) -> None:
    csv_path = settings.raw_dir / "epa_sld" / "sld_v3.csv"

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.headers = {"content-length": "100"}
    mock_resp.iter_content.return_value = [
        _csv_bytes(),
    ]

    with patch("urbanstack.extract.epa_sld.requests.get", return_value=mock_resp):
        from urbanstack.extract.epa_sld import _download_csv

        _download_csv(csv_path)

    assert csv_path.exists()


def _csv_bytes() -> bytes:
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    writer.writerow(DALLAS_ROW)
    return buf.getvalue().encode()


def test_column_rename_mapping(settings: Settings, metro: MetroConfig) -> None:
    csv_path = settings.raw_dir / "epa_sld" / "sld_v3.csv"
    _write_mock_csv(csv_path)

    with patch("urbanstack.extract.epa_sld._download_csv"):
        df = extract_epa_sld(settings, metro, force=True)

    expected_cols = {
        "geoid",
        "state_fips",
        "county_fips",
        "tract_fips",
        "cbsa",
        "d1a",
        "d1b",
        "d1c",
        "d2a_jphh",
        "d2b_e8mixa",
        "d3b",
        "d5dr",
        "d5de",
        "d4a",
        "d4d",
        "nat_walk_ind",
        "pct_ao0",
        "autoown",
    }
    assert set(df.columns) == expected_cols
