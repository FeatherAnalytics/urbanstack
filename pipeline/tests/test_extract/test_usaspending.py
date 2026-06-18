from unittest.mock import MagicMock, patch

import polars as pl

from urbanstack.config import Settings
from urbanstack.extract.usaspending import (
    GRANT_AWARD_CODES,
    extract_usaspending,
)
from urbanstack.geography import DFW_COUNTY_FIPS, DFW_STATE_FIPS


def _make_result(
    shape_code: str = "48113",
    display_name: str = "Dallas",
    aggregated_amount: float = 1234567.89,
    population: int = 2613539,
    per_capita: float = 0.47,
) -> dict:
    return {
        "shape_code": shape_code,
        "display_name": display_name,
        "aggregated_amount": aggregated_amount,
        "population": population,
        "per_capita": per_capita,
    }


def _mock_post_response(results: list[dict]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "scope": "place_of_performance",
        "geo_layer": "county",
        "results": results,
    }
    return mock_resp


def test_county_fips_list() -> None:
    fips_list = [f"{DFW_STATE_FIPS}{fips}" for fips in DFW_COUNTY_FIPS.values()]
    assert "48113" in fips_list  # Dallas
    assert "48085" in fips_list  # Collin
    assert "48439" in fips_list  # Tarrant
    assert all(len(f) == 5 for f in fips_list)
    assert all(f.startswith("48") for f in fips_list)


def test_extract_basic(settings: Settings) -> None:
    results = [
        _make_result(shape_code="48113", display_name="Dallas"),
        _make_result(shape_code="48085", display_name="Collin", aggregated_amount=999.99),
    ]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings)

    assert isinstance(df, pl.DataFrame)
    assert "county_fips" in df.columns
    assert "county_name" in df.columns
    assert "total_obligation" in df.columns
    assert "per_capita" in df.columns
    assert "population" in df.columns
    assert len(df) == 2


def test_amount_mapping(settings: Settings) -> None:
    results = [
        _make_result(aggregated_amount=5000000.50),
        _make_result(shape_code="48085", aggregated_amount=123.45),
    ]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings)

    amounts = sorted(df["total_obligation"].to_list())
    assert 123.45 in amounts
    assert 5000000.50 in amounts


def test_null_amount_skipped(settings: Settings) -> None:
    results = [
        _make_result(),
        {"shape_code": "48121", "display_name": "Denton", "aggregated_amount": None},
    ]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings)

    assert len(df) == 1
    assert df["county_fips"].to_list() == ["48113"]


def test_invalid_shape_code_skipped(settings: Settings) -> None:
    results = [
        _make_result(),
        {"shape_code": "48", "display_name": "Bad", "aggregated_amount": 100.0},
    ]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings)

    assert len(df) == 1


def test_fiscal_year_fields(settings: Settings) -> None:
    results = [_make_result()]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings, start_year=2021, end_year=2023)

    assert df["fiscal_year_start"].to_list() == ["2021-10-01"]
    assert df["fiscal_year_end"].to_list() == ["2023-09-30"]


def test_defc_filter(settings: Settings) -> None:
    results = [_make_result()]
    mock_resp = _mock_post_response(results)

    patch_target = "urbanstack.extract.usaspending.requests.post"
    with patch(patch_target, return_value=mock_resp) as mock_post:
        extract_usaspending(settings, defc="Z")

    call_args = mock_post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["filters"]["def_codes"] == ["Z"]


def test_no_defc_by_default(settings: Settings) -> None:
    results = [_make_result()]
    mock_resp = _mock_post_response(results)

    patch_target = "urbanstack.extract.usaspending.requests.post"
    with patch(patch_target, return_value=mock_resp) as mock_post:
        extract_usaspending(settings)

    call_args = mock_post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert "def_codes" not in body["filters"]


def test_post_body_structure(settings: Settings) -> None:
    results = [_make_result()]
    mock_resp = _mock_post_response(results)

    patch_target = "urbanstack.extract.usaspending.requests.post"
    with patch(patch_target, return_value=mock_resp) as mock_post:
        extract_usaspending(settings)

    call_args = mock_post.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body["scope"] == "place_of_performance"
    assert body["geo_layer"] == "county"
    assert body["filters"]["award_type_codes"] == GRANT_AWARD_CODES
    assert len(body["geo_layer_filters"]) == 12


def test_idempotent_skip(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "usaspending"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "usaspending_dfw_2020_2024.parquet"
    existing = pl.DataFrame({"county_fips": ["48113"], "county_name": ["Dallas"]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.usaspending.requests.post") as mock_post:
        df = extract_usaspending(settings)
        mock_post.assert_not_called()

    assert len(df) == 1


def test_force_overwrite(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "usaspending"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "usaspending_dfw_2020_2024.parquet"
    existing = pl.DataFrame({"county_fips": ["old"], "county_name": ["Old"]})
    existing.write_parquet(parquet_path)

    results = [_make_result()]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings, force=True)

    assert "48113" in df["county_fips"].to_list()
    assert "old" not in df["county_fips"].to_list()


def test_raw_json_saved(settings: Settings) -> None:
    results = [_make_result()]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        extract_usaspending(settings)

    raw_path = settings.raw_dir / "usaspending" / "usaspending_dfw_2020_2024.json"
    assert raw_path.exists()


def test_contract_validation(settings: Settings) -> None:
    results = [_make_result()]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings)

    from urbanstack.contracts.usaspending import UsaspendingCountyRecord

    row_dict = df.to_dicts()[0]
    record = UsaspendingCountyRecord.model_validate(row_dict)
    assert record.county_fips == "48113"
    assert record.total_obligation == 1234567.89
    assert record.population == 2613539


def test_per_capita_optional(settings: Settings) -> None:
    results = [
        {
            "shape_code": "48113",
            "display_name": "Dallas",
            "aggregated_amount": 500.0,
            "population": None,
            "per_capita": None,
        }
    ]
    mock_resp = _mock_post_response(results)

    with patch("urbanstack.extract.usaspending.requests.post", return_value=mock_resp):
        df = extract_usaspending(settings)

    assert len(df) == 1
    assert df["per_capita"].to_list() == [None]
    assert df["population"].to_list() == [None]
