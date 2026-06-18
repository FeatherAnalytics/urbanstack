import json
import logging

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.usaspending import UsaspendingCountyRecord
from urbanstack.geography import DFW_COUNTY_FIPS, DFW_STATE_FIPS

logger = logging.getLogger(__name__)

SPENDING_BY_GEOGRAPHY_URL = "https://api.usaspending.gov/api/v2/search/spending_by_geography/"

GRANT_AWARD_CODES = ["02", "03", "04", "05"]


def _to_records(
    results: list[dict],
    start_date: str,
    end_date: str,
) -> list[UsaspendingCountyRecord]:
    records: list[UsaspendingCountyRecord] = []
    for item in results:
        shape_code = item.get("shape_code", "")
        if not shape_code or len(shape_code) != 5:
            continue

        amount = item.get("aggregated_amount")
        if amount is None:
            continue

        population = item.get("population")
        per_capita = item.get("per_capita")

        records.append(
            UsaspendingCountyRecord.model_validate(
                {
                    "county_fips": shape_code,
                    "county_name": item.get("display_name", ""),
                    "total_obligation": float(amount),
                    "per_capita": float(per_capita) if per_capita is not None else None,
                    "population": int(population) if population is not None else None,
                    "fiscal_year_start": start_date,
                    "fiscal_year_end": end_date,
                }
            )
        )
    return records


def extract_usaspending(
    settings: Settings,
    start_year: int = 2020,
    end_year: int = 2024,
    *,
    defc: str | None = None,
    force: bool = False,
) -> pl.DataFrame:
    parquet_dir = settings.staging_dir / "usaspending"
    suffix = f"_defc_{defc}" if defc else ""
    parquet_path = parquet_dir / f"usaspending_dfw_{start_year}_{end_year}{suffix}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    county_fips_list = [f"{DFW_STATE_FIPS}{fips}" for fips in DFW_COUNTY_FIPS.values()]
    start_date = f"{start_year}-10-01"
    end_date = f"{end_year}-09-30"

    filters: dict = {
        "time_period": [{"start_date": start_date, "end_date": end_date}],
        "award_type_codes": GRANT_AWARD_CODES,
    }
    if defc:
        filters["def_codes"] = [defc]

    body = {
        "scope": "place_of_performance",
        "geo_layer": "county",
        "geo_layer_filters": county_fips_list,
        "filters": filters,
    }

    resp = requests.post(SPENDING_BY_GEOGRAPHY_URL, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    raw_dir = settings.raw_dir / "usaspending"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"usaspending_dfw_{start_year}_{end_year}{suffix}.json"
    raw_path.write_text(json.dumps(data, indent=2))

    results = data.get("results", [])
    records = _to_records(results, start_date, end_date)
    row_dicts = [r.model_dump() for r in records]
    df = pl.DataFrame(row_dicts)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
