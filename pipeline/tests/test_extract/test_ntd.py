from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.extract.ntd import extract_ntd
from urbanstack.metro import MetroConfig

REQUESTS_PATCH = "urbanstack.extract._socrata.requests.get"


@pytest.fixture(autouse=True)
def _no_sleep():
    with (
        patch("urbanstack.extract.ntd.time.sleep"),
        patch("urbanstack.extract._socrata.time.sleep"),
    ):
        yield


def _make_row(
    ntd_id: str = "60056",
    agency: str = "Dallas Area Rapid Transit",
    mode: str = "LR",
    date: str = "2023-06-01T00:00:00.000",
    upt: str = "1500000",
    vrm: str = "500000",
    vrh: str = "25000",
) -> dict[str, str]:
    return {
        "ntd_id": ntd_id,
        "agency": agency,
        "mode": mode,
        "date": date,
        "upt": upt,
        "vrm": vrm,
        "vrh": vrh,
    }


def _mock_get_single_page(rows: list[dict[str, str]]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = rows
    return mock_resp


def test_extract_basic(settings: Settings, metro: MetroConfig) -> None:
    rows = [
        _make_row(ntd_id="60056", mode="LR"),
        _make_row(ntd_id="60056", mode="MB", upt="3000000"),
    ]
    mock_resp = _mock_get_single_page(rows)

    with patch(REQUESTS_PATCH, return_value=mock_resp):
        df = extract_ntd(settings, metro)

    assert isinstance(df, pl.DataFrame)
    assert "ntd_id" in df.columns
    assert "agency_name" in df.columns
    assert "mode" in df.columns
    assert "unlinked_passenger_trips" in df.columns


def test_dfw_agencies_only(settings: Settings, metro: MetroConfig) -> None:
    dart_row = _make_row(ntd_id="60056", agency="Dallas Area Rapid Transit")
    fwta_row = _make_row(ntd_id="60007", agency="Fort Worth Transportation Authority")
    dcta_row = _make_row(ntd_id="60101", agency="Denton County Transportation Authority")

    def side_effect(*args, **kwargs):
        params = kwargs.get("params", {})
        where = params.get("$where", "")
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        if "'60056'" in where:
            mock.json.return_value = [dart_row]
        elif "'60007'" in where:
            mock.json.return_value = [fwta_row]
        elif "'60101'" in where:
            mock.json.return_value = [dcta_row]
        else:
            mock.json.return_value = []
        return mock

    with patch(REQUESTS_PATCH, side_effect=side_effect):
        df = extract_ntd(settings, metro)

    ntd_ids = set(df["ntd_id"].to_list())
    assert ntd_ids == {"60056", "60007", "60101"}
    assert len(df) == 3


def test_mode_parsing(settings: Settings, metro: MetroConfig) -> None:
    rows = [
        _make_row(mode="LR"),
        _make_row(mode="MB", upt="3000000"),
        _make_row(mode="DR", upt="50000"),
    ]
    mock_resp = _mock_get_single_page(rows)

    with patch(REQUESTS_PATCH, return_value=mock_resp):
        df = extract_ntd(settings, metro)

    modes = set(df["mode"].to_list())
    assert modes == {"LR", "MB", "DR"}


def _side_effect_single_agency(rows: list[dict[str, str]], ntd_id: str = "60056"):
    def side_effect(*args, **kwargs):
        params = kwargs.get("params", {})
        where = params.get("$where", "")
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        if f"'{ntd_id}'" in where:
            mock.json.return_value = rows
        else:
            mock.json.return_value = []
        return mock

    return side_effect


def test_date_parsing(settings: Settings, metro: MetroConfig) -> None:
    rows = [_make_row(date="2023-06-01T00:00:00.000")]

    with patch(
        REQUESTS_PATCH,
        side_effect=_side_effect_single_agency(rows),
    ):
        df = extract_ntd(settings, metro)

    assert df["year"].to_list() == [2023]
    assert df["month"].to_list() == [6]


def test_null_upt_accepted(settings: Settings, metro: MetroConfig) -> None:
    row = _make_row()
    row["upt"] = None

    with patch(
        REQUESTS_PATCH,
        side_effect=_side_effect_single_agency([row]),
    ):
        df = extract_ntd(settings, metro)

    assert len(df) == 1
    assert df["unlinked_passenger_trips"].to_list() == [None]


def test_missing_date_skipped(settings: Settings, metro: MetroConfig) -> None:
    good_row = _make_row()
    bad_row = _make_row()
    bad_row["date"] = ""

    with patch(
        REQUESTS_PATCH,
        side_effect=_side_effect_single_agency([good_row, bad_row]),
    ):
        df = extract_ntd(settings, metro)

    assert len(df) == 1


def test_malformed_date_skipped(settings: Settings, metro: MetroConfig) -> None:
    """Malformed date strings should be skipped, not crash."""
    good_row = _make_row()
    bad_row = _make_row()
    bad_row["date"] = "bad"

    with patch(
        REQUESTS_PATCH,
        side_effect=_side_effect_single_agency([good_row, bad_row]),
    ):
        df = extract_ntd(settings, metro)

    assert len(df) == 1


def test_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "ntd"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"ntd_{metro.metro_id}.parquet"
    existing = pl.DataFrame({"ntd_id": ["60056"], "agency_name": ["DART"]})
    existing.write_parquet(parquet_path)

    with patch(REQUESTS_PATCH) as mock_get:
        df = extract_ntd(settings, metro)
        mock_get.assert_not_called()

    assert len(df) == 1


def test_force_overwrite(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "ntd"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / f"ntd_{metro.metro_id}.parquet"
    existing = pl.DataFrame({"ntd_id": ["old"], "agency_name": ["Old Agency"]})
    existing.write_parquet(parquet_path)

    rows = [_make_row()]
    mock_resp = _mock_get_single_page(rows)

    with patch(REQUESTS_PATCH, return_value=mock_resp):
        df = extract_ntd(settings, metro, force=True)

    assert "60056" in df["ntd_id"].to_list()
    assert "old" not in df["ntd_id"].to_list()


def test_pagination(settings: Settings, metro: MetroConfig) -> None:
    page1 = [_make_row(date=f"2023-{i % 12 + 1:02d}-01T00:00:00.000") for i in range(50000)]
    page2 = [_make_row(date="2023-12-01T00:00:00.000")]

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        params = kwargs.get("params", {})
        offset = int(params.get("$offset", "0"))
        where = params.get("$where", "")

        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        if "'60056'" in where and offset == 0:
            mock.json.return_value = page1
        elif "'60056'" in where and offset == 50000:
            mock.json.return_value = page2
        else:
            mock.json.return_value = []
        return mock

    with patch(REQUESTS_PATCH, side_effect=side_effect):
        df = extract_ntd(settings, metro)

    assert len(df) == 50001


def test_raw_json_saved(settings: Settings, metro: MetroConfig) -> None:
    rows = [_make_row()]
    mock_resp = _mock_get_single_page(rows)

    with patch(REQUESTS_PATCH, return_value=mock_resp):
        extract_ntd(settings, metro)

    raw_path = settings.metro_raw_dir(metro.metro_id) / "ntd" / f"ntd_{metro.metro_id}.json"
    assert raw_path.exists()


def test_contract_validation(settings: Settings, metro: MetroConfig) -> None:
    rows = [_make_row()]
    mock_resp = _mock_get_single_page(rows)

    with patch(REQUESTS_PATCH, return_value=mock_resp):
        df = extract_ntd(settings, metro)

    from urbanstack.contracts.ntd import NtdRidershipRecord

    row_dict = df.to_dicts()[0]
    record = NtdRidershipRecord.model_validate(row_dict)
    assert record.ntd_id == "60056"
    assert record.unlinked_passenger_trips == 1500000


def test_metro_transit_agency_ids(metro: MetroConfig) -> None:
    assert "60056" in metro.transit_agencies
    assert "60007" in metro.transit_agencies
    assert "60101" in metro.transit_agencies
    assert len(metro.transit_agencies) == 3
