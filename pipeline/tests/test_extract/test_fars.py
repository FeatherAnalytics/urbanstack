import csv
import io
import zipfile
from unittest.mock import MagicMock, patch

import polars as pl

from urbanstack.config import Settings
from urbanstack.extract.fars import extract_fars
from urbanstack.metro import MetroConfig

ACCIDENT_FIELDS = [
    "ST_CASE", "STATE", "COUNTY", "YEAR", "MONTH",
    "FATALS", "PERSONS", "PEDS", "DRUNK_DR", "LATITUDE", "LONGITUD",
]


def _make_row(
    st_case: int = 480001,
    state: int = 48,
    county: int = 113,
    year: int = 2022,
    month: int = 6,
    fatals: int = 1,
    persons: int = 3,
    peds: int = 0,
    drunk_dr: int = 0,
    latitude: float = 32.7767,
    longitude: float = -96.7970,
) -> dict[str, object]:
    return {
        "ST_CASE": st_case,
        "STATE": state,
        "COUNTY": county,
        "YEAR": year,
        "MONTH": month,
        "FATALS": fatals,
        "PERSONS": persons,
        "PEDS": peds,
        "DRUNK_DR": drunk_dr,
        "LATITUDE": latitude,
        "LONGITUD": longitude,
    }


def _make_zip_bytes(rows: list[dict[str, object]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ACCIDENT_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    csv_content = buf.getvalue()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("ACCIDENT.CSV", csv_content)
    return zip_buf.getvalue()


def _mock_get_response(rows: list[dict[str, object]]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = _make_zip_bytes(rows)
    return mock_resp


def test_extract_basic(settings: Settings, metro: MetroConfig) -> None:
    rows = [_make_row(), _make_row(st_case=480002, fatals=2)]
    mock_resp = _mock_get_response(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    assert isinstance(df, pl.DataFrame)
    assert "case_id" in df.columns
    assert "state_fips" in df.columns
    assert "county_fips" in df.columns
    assert "fatalities" in df.columns
    assert all(v == "48" for v in df["state_fips"].to_list())


def test_county_filtering(settings: Settings, metro: MetroConfig) -> None:
    rows = [
        _make_row(st_case=480001, county=113),  # Dallas — in DFW
        _make_row(st_case=480002, county=439),  # Tarrant — in DFW
        _make_row(st_case=480003, county=201),  # Harris — not in DFW
    ]
    mock_resp = _mock_get_response(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    county_fips = set(df["county_fips"].to_list())
    assert "113" in county_fips
    assert "439" in county_fips
    assert "201" not in county_fips


def test_fatality_counts(settings: Settings, metro: MetroConfig) -> None:
    rows = [
        _make_row(st_case=480001, fatals=1),
        _make_row(st_case=480002, fatals=3),
    ]
    mock_resp = _mock_get_response(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    fatals = sorted(df["fatalities"].to_list())
    assert 1 in fatals
    assert 3 in fatals


def test_year_range(settings: Settings, metro: MetroConfig) -> None:
    mock_resp = _mock_get_response([])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp) as mock_get:
        extract_fars(settings, metro, start_year=2020, end_year=2022)

    assert mock_get.call_count == 3


def test_zero_padded_county(settings: Settings, metro: MetroConfig) -> None:
    row = _make_row(county=85)  # Collin = 085
    mock_resp = _mock_get_response([row])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    counties = df["county_fips"].to_list()
    assert "085" in counties


def test_sentinel_coords_nullified(settings: Settings, metro: MetroConfig) -> None:
    row = _make_row(latitude=77.7777, longitude=88.8888)
    mock_resp = _mock_get_response([row])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    assert df["latitude"].to_list() == [None]
    assert df["longitude"].to_list() == [None]


def test_missing_month_skipped(settings: Settings, metro: MetroConfig) -> None:
    """Rows with empty month should be skipped by the guard in _to_records."""
    good_row = _make_row(st_case=480001, month=6)
    # CSV empty-string month triggers `if not month` guard
    bad_row: dict[str, object] = dict(_make_row(st_case=480002))
    bad_row["MONTH"] = ""
    mock_resp = _mock_get_response([good_row, bad_row])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    case_ids = df["case_id"].to_list()
    assert 480001 in case_ids
    assert 480002 not in case_ids


def test_zero_fatals_skipped(settings: Settings, metro: MetroConfig) -> None:
    rows = [
        _make_row(st_case=480001, fatals=1),
        _make_row(st_case=480002, fatals=0),
    ]
    mock_resp = _mock_get_response(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    case_ids = df["case_id"].to_list()
    assert 480001 in case_ids
    assert 480002 not in case_ids


def test_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "fars"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"fars_{metro.metro_id}_2022_2022.parquet"
    existing = pl.DataFrame({"case_id": [480001], "state_fips": ["48"]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.fars.requests.get") as mock_get:
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)
        mock_get.assert_not_called()

    assert len(df) == 1


def test_force_overwrite(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "fars"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"fars_{metro.metro_id}_2022_2022.parquet"
    existing = pl.DataFrame({"case_id": [999999], "state_fips": ["48"]})
    existing.write_parquet(parquet_path)

    rows = [_make_row(st_case=480001)]
    mock_resp = _mock_get_response(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022, force=True)

    assert 480001 in df["case_id"].to_list()
    assert 999999 not in df["case_id"].to_list()


def test_contract_validation(settings: Settings, metro: MetroConfig) -> None:
    rows = [_make_row()]
    mock_resp = _mock_get_response(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    from urbanstack.contracts.fars import FarsCrashRecord

    row_dict = df.to_dicts()[0]
    record = FarsCrashRecord.model_validate(row_dict)
    assert record.case_id == 480001
    assert record.state_fips == "48"
    assert record.county_fips == "113"
    assert record.fatalities == 1


def test_longitud_vs_longitude_field(settings: Settings, metro: MetroConfig) -> None:
    row = _make_row()
    del row["LONGITUD"]
    row["LONGITUDE"] = -96.7970
    # Need custom CSV fields for this test
    fields = [f for f in ACCIDENT_FIELDS if f != "LONGITUD"] + ["LONGITUDE"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerow(row)
    csv_content = buf.getvalue()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("ACCIDENT.CSV", csv_content)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = zip_buf.getvalue()

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    assert df["longitude"].to_list()[0] is not None


def test_null_optional_fields(settings: Settings, metro: MetroConfig) -> None:
    row = _make_row()
    row["PERSONS"] = ""
    row["PEDS"] = ""
    row["DRUNK_DR"] = ""
    mock_resp = _mock_get_response([row])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, metro, start_year=2022, end_year=2022)

    assert len(df) == 1
    assert df["persons"].to_list() == [None]
    assert df["pedestrians"].to_list() == [None]
    assert df["drunk_drivers"].to_list() == [None]
