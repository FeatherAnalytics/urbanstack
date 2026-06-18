from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.extract.fhwa import extract_fhwa


@pytest.fixture(autouse=True)
def _no_sleep():
    with (
        patch("urbanstack.extract.fhwa.time.sleep"),
        patch("urbanstack.extract._socrata.time.sleep"),
    ):
        yield


def _make_row(
    station_id: str = "000004",
    month: str = "1",
    day: str = "15",
    daily_volume: str = "133732",
    fsystem_cd: str = "1",
    rural_urban: str = "U",
    year: str = "2023",
) -> dict[str, str]:
    return {
        "station_id": station_id,
        "fsystem_cd": fsystem_cd,
        "rural_urban": rural_urban,
        "year": year,
        "month": month,
        "day": day,
        "daily_volume": daily_volume,
    }


def _mock_get_single_page(rows: list[dict[str, str]]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = rows
    return mock_resp


def test_extract_basic(settings: Settings) -> None:
    rows = [
        _make_row(station_id="000004", month="1", day="15"),
        _make_row(station_id="000006", month="1", day="15", daily_volume="4417"),
    ]

    mock_resp = _mock_get_single_page(rows)
    empty_resp = _mock_get_single_page([])

    responses = []
    for _ in range(12):
        if not responses:
            responses.append(mock_resp)
        else:
            responses.append(empty_resp)
    responses[0] = mock_resp

    with patch("urbanstack.extract._socrata.requests.get", return_value=mock_resp) as mock_get:
        mock_get.side_effect = None
        mock_get.return_value = mock_resp
        df = extract_fhwa(settings, year=2023)

    assert isinstance(df, pl.DataFrame)
    assert "station_id" in df.columns
    assert "daily_volume" in df.columns
    assert "state_fips" in df.columns
    assert all(v == "48" for v in df["state_fips"].to_list())


def test_daily_volume_values(settings: Settings) -> None:
    rows = [
        _make_row(daily_volume="133732"),
        _make_row(station_id="000006", daily_volume="4417"),
    ]
    mock_resp = _mock_get_single_page(rows)

    with patch("urbanstack.extract._socrata.requests.get", return_value=mock_resp):
        df = extract_fhwa(settings, year=2023)

    volumes = sorted(df["daily_volume"].to_list())
    assert 4417 in volumes
    assert 133732 in volumes


def test_null_volume_skipped(settings: Settings) -> None:
    rows = [
        _make_row(daily_volume="100"),
        {
            "station_id": "000099",
            "fsystem_cd": "2",
            "rural_urban": "R",
            "year": "2023",
            "month": "1",
            "day": "15",
            "daily_volume": None,
        },
    ]
    mock_resp = _mock_get_single_page(rows)

    with patch("urbanstack.extract._socrata.requests.get", return_value=mock_resp):
        df = extract_fhwa(settings, year=2023)

    assert len(df) > 0
    station_ids = df["station_id"].to_list()
    assert "000099" not in station_ids


def test_pagination(settings: Settings) -> None:
    import re

    page1 = [_make_row(station_id=f"{i:06d}") for i in range(50000)]
    page2 = [_make_row(station_id="099999")]

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        params = kwargs.get("params", {})
        offset = int(params.get("$offset", "0"))
        where = params.get("$where", "")
        match = re.search(r"month='(\d+)'", where)
        month = match.group(1) if match else "0"

        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        if month == "1" and offset == 0:
            mock.json.return_value = page1
        elif month == "1" and offset == 50000:
            mock.json.return_value = page2
        else:
            mock.json.return_value = []
        return mock

    with patch("urbanstack.extract._socrata.requests.get", side_effect=side_effect):
        df = extract_fhwa(settings, year=2023)

    assert len(df) == 50001
    assert call_count > 12


def test_idempotent_skip(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "fhwa"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "fhwa_tx_2023.parquet"
    existing = pl.DataFrame({"station_id": ["000004"], "state_fips": ["48"]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract._socrata.requests.get") as mock_get:
        df = extract_fhwa(settings, year=2023)
        mock_get.assert_not_called()

    assert len(df) == 1


def test_force_overwrite(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "fhwa"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "fhwa_tx_2023.parquet"
    existing = pl.DataFrame({"station_id": ["old"], "state_fips": ["48"]})
    existing.write_parquet(parquet_path)

    rows = [_make_row(station_id="000004")]
    mock_resp = _mock_get_single_page(rows)

    with patch("urbanstack.extract._socrata.requests.get", return_value=mock_resp):
        df = extract_fhwa(settings, year=2023, force=True)

    assert "000004" in df["station_id"].to_list()
    assert "old" not in df["station_id"].to_list()


def test_invalid_year_raises() -> None:
    from urbanstack.extract.fhwa import _dataset_url

    with pytest.raises(ValueError, match="No TMAS dataset"):
        _dataset_url(2010)


def test_contract_validation(settings: Settings) -> None:
    rows = [_make_row()]
    mock_resp = _mock_get_single_page(rows)

    with patch("urbanstack.extract._socrata.requests.get", return_value=mock_resp):
        df = extract_fhwa(settings, year=2023)

    from urbanstack.contracts.fhwa import FhwaVolumeRecord

    row_dict = df.to_dicts()[0]
    record = FhwaVolumeRecord.model_validate(row_dict)
    assert record.station_id == "000004"
    assert record.state_fips == "48"
    assert record.daily_volume == 133732


def test_raw_json_saved(settings: Settings) -> None:
    rows = [_make_row()]
    mock_resp = _mock_get_single_page(rows)

    with patch("urbanstack.extract._socrata.requests.get", return_value=mock_resp):
        extract_fhwa(settings, year=2023)

    raw_path = settings.raw_dir / "fhwa" / "fhwa_tx_2023.json"
    assert raw_path.exists()
