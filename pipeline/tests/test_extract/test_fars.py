from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.extract.fars import extract_fars


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("urbanstack.extract.fars.time.sleep"):
        yield


def _make_row(
    st_case: int = 480001,
    county: int = 113,
    year: int = 2022,
    month: int = 6,
    fatals: int = 1,
    persons: int = 3,
    peds: int = 0,
    drunk_dr: int = 0,
    latitude: float = 32.7767,
    longitude: float = -96.7970,
) -> dict:
    return {
        "ST_CASE": st_case,
        "STATE": 48,
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


def _mock_get_rows(rows: list[dict]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"Results": [{"Results": rows}]}
    return mock_resp


def _mock_get_empty() -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"Results": [{"Results": []}]}
    return mock_resp


def test_extract_basic(settings: Settings) -> None:
    rows = [_make_row(), _make_row(st_case=480002, fatals=2)]
    mock_resp = _mock_get_rows(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    assert isinstance(df, pl.DataFrame)
    assert "case_id" in df.columns
    assert "state_fips" in df.columns
    assert "county_fips" in df.columns
    assert "fatalities" in df.columns
    assert all(v == "48" for v in df["state_fips"].to_list())


def test_county_filtering(settings: Settings) -> None:
    dallas_row = _make_row(st_case=480001, county=113)
    tarrant_row = _make_row(st_case=480002, county=439)
    harris_row = _make_row(st_case=480003, county=201)

    def side_effect(*args, **kwargs):
        params = kwargs.get("params", {})
        county = params.get("county")
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        if county == 113:
            mock.json.return_value = {"Results": [{"Results": [dallas_row]}]}
        elif county == 439:
            mock.json.return_value = {"Results": [{"Results": [tarrant_row]}]}
        elif county == 201:
            mock.json.return_value = {"Results": [{"Results": [harris_row]}]}
        else:
            mock.json.return_value = {"Results": [{"Results": []}]}
        return mock

    with patch("urbanstack.extract.fars.requests.get", side_effect=side_effect):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    county_fips = set(df["county_fips"].to_list())
    assert "113" in county_fips
    assert "439" in county_fips
    assert "201" not in county_fips


def test_fatality_counts(settings: Settings) -> None:
    rows = [
        _make_row(st_case=480001, fatals=1),
        _make_row(st_case=480002, fatals=3),
    ]
    mock_resp = _mock_get_rows(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    fatals = sorted(df["fatalities"].to_list())
    assert 1 in fatals
    assert 3 in fatals


def test_year_range(settings: Settings) -> None:
    call_years: list[int] = []

    def side_effect(*args, **kwargs):
        params = kwargs.get("params", {})
        call_years.append(params.get("fromCaseYear"))
        return _mock_get_empty()

    with patch("urbanstack.extract.fars.requests.get", side_effect=side_effect):
        extract_fars(settings, start_year=2020, end_year=2022)

    assert 2020 in call_years
    assert 2021 in call_years
    assert 2022 in call_years


def test_zero_padded_county(settings: Settings) -> None:
    row = _make_row(county=85)
    mock_resp = _mock_get_rows([row])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    counties = df["county_fips"].to_list()
    assert "085" in counties


def test_sentinel_coords_nullified(settings: Settings) -> None:
    row = _make_row(latitude=77.7777, longitude=88.8888)

    def side_effect(*args, **kwargs):
        params = kwargs.get("params", {})
        county = params.get("county")
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        if county == 113:
            mock.json.return_value = {"Results": [{"Results": [row]}]}
        else:
            mock.json.return_value = {"Results": [{"Results": []}]}
        return mock

    with patch("urbanstack.extract.fars.requests.get", side_effect=side_effect):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    assert df["latitude"].to_list() == [None]
    assert df["longitude"].to_list() == [None]


def test_missing_month_skipped(settings: Settings) -> None:
    """Rows with missing/zero month should be skipped (would violate contract ge=1)."""
    good_row = _make_row(st_case=480001, month=6)
    bad_row_zero = _make_row(st_case=480002, month=0)
    bad_row_none = _make_row(st_case=480003)
    bad_row_none["MONTH"] = None
    mock_resp = _mock_get_rows([good_row, bad_row_zero, bad_row_none])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    case_ids = df["case_id"].to_list()
    assert 480001 in case_ids
    assert 480002 not in case_ids
    assert 480003 not in case_ids


def test_zero_fatals_skipped(settings: Settings) -> None:
    rows = [
        _make_row(st_case=480001, fatals=1),
        _make_row(st_case=480002, fatals=0),
    ]
    mock_resp = _mock_get_rows(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    case_ids = df["case_id"].to_list()
    assert 480001 in case_ids
    assert 480002 not in case_ids


def test_idempotent_skip(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "fars"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "fars_dfw_2022_2022.parquet"
    existing = pl.DataFrame({"case_id": [480001], "state_fips": ["48"]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.fars.requests.get") as mock_get:
        df = extract_fars(settings, start_year=2022, end_year=2022)
        mock_get.assert_not_called()

    assert len(df) == 1


def test_force_overwrite(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "fars"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "fars_dfw_2022_2022.parquet"
    existing = pl.DataFrame({"case_id": [999999], "state_fips": ["48"]})
    existing.write_parquet(parquet_path)

    rows = [_make_row(st_case=480001)]
    mock_resp = _mock_get_rows(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022, force=True)

    assert 480001 in df["case_id"].to_list()
    assert 999999 not in df["case_id"].to_list()


def test_raw_json_saved(settings: Settings) -> None:
    rows = [_make_row()]
    mock_resp = _mock_get_rows(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        extract_fars(settings, start_year=2022, end_year=2022)

    raw_path = settings.raw_dir / "fars" / "fars_dfw_2022_2022.json"
    assert raw_path.exists()


def test_contract_validation(settings: Settings) -> None:
    rows = [_make_row()]
    mock_resp = _mock_get_rows(rows)

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    from urbanstack.contracts.fars import FarsCrashRecord

    row_dict = df.to_dicts()[0]
    record = FarsCrashRecord.model_validate(row_dict)
    assert record.case_id == 480001
    assert record.state_fips == "48"
    assert record.county_fips == "113"
    assert record.fatalities == 1


def test_longitud_vs_longitude_field(settings: Settings) -> None:
    row = _make_row()
    del row["LONGITUD"]
    row["LONGITUDE"] = -96.7970
    mock_resp = _mock_get_rows([row])

    with patch("urbanstack.extract.fars.requests.get", return_value=mock_resp):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    assert df["longitude"].to_list()[0] is not None


def test_null_optional_fields(settings: Settings) -> None:
    row = _make_row()
    row["PERSONS"] = None
    row["PEDS"] = None
    row["DRUNK_DR"] = None

    def side_effect(*args, **kwargs):
        params = kwargs.get("params", {})
        county = params.get("county")
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        if county == 113:
            mock.json.return_value = {"Results": [{"Results": [row]}]}
        else:
            mock.json.return_value = {"Results": [{"Results": []}]}
        return mock

    with patch("urbanstack.extract.fars.requests.get", side_effect=side_effect):
        df = extract_fars(settings, start_year=2022, end_year=2022)

    assert len(df) == 1
    assert df["persons"].to_list() == [None]
    assert df["pedestrians"].to_list() == [None]
    assert df["drunk_drivers"].to_list() == [None]
