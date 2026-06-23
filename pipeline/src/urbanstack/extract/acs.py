import json
import logging
import time

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.acs import AcsRecord, Granularity
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)

ACS_BASE_URL = "https://api.census.gov/data/{year}/acs/acs5"

ACS_VARIABLES: dict[str, str] = {
    "B01003_001E": "total_population",
    "B19301_001E": "per_capita_income",
    "B19013_001E": "median_household_income",
    "B08301_003E": "commute_drove_alone",
    "B08301_010E": "commute_transit",
    "B08301_019E": "commute_walked",
    "B08301_018E": "commute_biked",
    "B08301_021E": "commute_wfh",
    "B25046_001E": "vehicles_available",
    "B25064_001E": "median_rent",
    "B25077_001E": "median_home_value",
}

SUPPRESSED = -666666666


def _fetch(
    url: str,
    params: list[tuple[str, str]] | dict[str, str],
    timeout: int = 30,
) -> list[list[str]]:
    """Shared HTTP helper: request + raise_for_status + HTML guard + JSON parse."""
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    if "text/html" in resp.headers.get("content-type", ""):
        raise ValueError(
            f"Census API returned HTML (likely invalid/inactive key): {resp.text[:200]}"
        )
    return resp.json()


def _parse_response(
    raw: list[list[str]],
    granularity: Granularity,
) -> list[AcsRecord]:
    headers = raw[0]
    records: list[AcsRecord] = []
    for row in raw[1:]:
        row_dict = dict(zip(headers, row, strict=False))
        kwargs: dict[str, str | int | None] = {
            "state_fips": row_dict["state"],
            "county_fips": row_dict["county"],
            "name": row_dict["NAME"],
        }
        if granularity == "block_group":
            kwargs["tract_fips"] = row_dict["tract"]
            kwargs["block_group_fips"] = row_dict["block group"]

        for var_code, field_name in ACS_VARIABLES.items():
            raw_val = row_dict[var_code]
            val = None if raw_val is None or raw_val == "" else int(raw_val)
            kwargs[field_name] = None if val == SUPPRESSED else val

        records.append(AcsRecord.model_validate(kwargs))
    return records


def _fetch_multi(
    url: str,
    param_batches: list[dict[str, str] | list[tuple[str, str]]],
) -> list[list[str]]:
    """Fetch multiple Census API pages, rate-limited, with header dedup."""
    if not param_batches:
        return []
    all_rows: list[list[str]] = []
    headers: list[str] | None = None
    for i, params in enumerate(param_batches):
        if i > 0:
            time.sleep(0.5)
        data = _fetch(url, params)
        if headers is None:
            headers = data[0]
            all_rows.append(headers)
        all_rows.extend(data[1:])
    return all_rows


def _fetch_county(url: str, api_key: str, metro: MetroConfig) -> list[list[str]]:
    batches: list[dict[str, str]] = []
    for state_fips, counties in metro.states.items():
        batches.append({
            "get": f"NAME,{','.join(ACS_VARIABLES.keys())}",
            "for": f"county:{','.join(counties.values())}",
            "in": f"state:{state_fips}",
            "key": api_key,
        })
    return _fetch_multi(url, batches)


def _fetch_block_groups(url: str, api_key: str, metro: MetroConfig) -> list[list[str]]:
    batches: list[list[tuple[str, str]]] = []
    for state_fips, counties in metro.states.items():
        for county_fips in counties.values():
            batches.append([
                ("get", f"NAME,{','.join(ACS_VARIABLES.keys())}"),
                ("for", "block group:*"),
                ("in", f"state:{state_fips}"),
                ("in", f"county:{county_fips}"),
                ("key", api_key),
            ])
    return _fetch_multi(url, batches)


ALL_STATE_FIPS = [
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12",
    "13", "15", "16", "17", "18", "19", "20", "21", "22", "23",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33",
    "34", "35", "36", "37", "38", "39", "40", "41", "42", "44",
    "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56",
]


def _fetch_county_national(url: str, api_key: str) -> list[list[str]]:
    return _fetch(url, {
        "get": f"NAME,{','.join(ACS_VARIABLES.keys())}",
        "for": "county:*",
        "key": api_key,
    })


def _fetch_block_groups_national(url: str, api_key: str) -> list[list[str]]:
    batches: list[list[tuple[str, str]]] = []
    for state_fips in ALL_STATE_FIPS:
        batches.append([
            ("get", f"NAME,{','.join(ACS_VARIABLES.keys())}"),
            ("for", "block group:*"),
            ("in", f"state:{state_fips} county:*"),
            ("key", api_key),
        ])
    return _fetch_multi(url, batches)


def extract_acs_national(
    settings: Settings,
    granularity: Granularity = "county",
    year: int = 2023,
    *,
    force: bool = False,
) -> pl.DataFrame:
    if not settings.census_api_key:
        raise ValueError("CENSUS_API_KEY is required")

    parquet_dir = settings.staging_dir / "national" / "acs"
    parquet_path = parquet_dir / f"acs_{granularity}_{year}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    url = ACS_BASE_URL.format(year=year)

    if granularity == "county":
        raw = _fetch_county_national(url, settings.census_api_key)
    else:
        raw = _fetch_block_groups_national(url, settings.census_api_key)

    raw_dir = settings.raw_dir / "national" / "acs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"acs_{granularity}_{year}.json"
    raw_path.write_text(json.dumps(raw, indent=2))

    records = _parse_response(raw, granularity)
    rows = [r.model_dump() for r in records]
    df = pl.DataFrame(rows)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df


def extract_acs(
    settings: Settings,
    metro: MetroConfig,
    granularity: Granularity = "county",
    year: int = 2023,
    *,
    force: bool = False,
) -> pl.DataFrame:
    if not settings.census_api_key:
        raise ValueError("CENSUS_API_KEY is required -- set it in .env or pass via Settings")

    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "acs"
    parquet_path = parquet_dir / f"acs_{granularity}_{year}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    url = ACS_BASE_URL.format(year=year)

    if granularity == "county":
        raw = _fetch_county(url, settings.census_api_key, metro)
    else:
        raw = _fetch_block_groups(url, settings.census_api_key, metro)

    raw_dir = settings.metro_raw_dir(metro.metro_id) / "acs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"acs_{granularity}_{year}.json"
    raw_path.write_text(json.dumps(raw, indent=2))

    records = _parse_response(raw, granularity)
    rows = [r.model_dump() for r in records]
    df = pl.DataFrame(rows)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
