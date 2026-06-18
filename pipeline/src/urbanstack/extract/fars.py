import json
import logging
import time

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.fars import FarsCrashRecord
from urbanstack.geography import DFW_COUNTY_FIPS, DFW_STATE_FIPS

logger = logging.getLogger(__name__)

FARS_BASE = "https://crashviewer.nhtsa.dot.gov/CrashAPI"


def _fetch_county_year(state: int, county: int, year: int) -> list[dict]:
    """Fetch crashes for one county+year via GetCrashesByLocation."""
    url = f"{FARS_BASE}/crashes/GetCrashesByLocation"
    params = {
        "fromCaseYear": year,
        "toCaseYear": year,
        "state": state,
        "county": county,
        "format": "json",
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict):
        for key in ("Results", "results"):
            if key in data:
                inner = data[key]
                if isinstance(inner, list) and len(inner) == 1 and isinstance(inner[0], dict):
                    return inner[0].get(key, inner)
                return inner
        return []

    return data if isinstance(data, list) else []


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_coordinate(val: object) -> float | None:
    """Parse a FARS lat/lon value, returning None for sentinel values.

    FARS uses 0.0, 77.7777, 88.8888, and 99.9999 as sentinel values
    indicating unknown or not-reported coordinates. These are invalid
    for U.S. geographic coordinates.
    """
    if val is None:
        return None
    try:
        f = float(val)
        return f if f not in (0.0, 99.9999, 77.7777, 88.8888) else None
    except (ValueError, TypeError):
        return None


def _to_records(
    raw_rows: list[dict],
    state_fips: str,
) -> list[FarsCrashRecord]:
    records: list[FarsCrashRecord] = []
    for row in raw_rows:
        fatals = _safe_int(row.get("FATALS"))
        if not fatals or fatals < 1:
            continue

        county_raw = row.get("COUNTY")
        if county_raw is None:
            continue
        county_fips = str(int(county_raw)).zfill(3)

        year = row.get("YEAR") or row.get("CaseYear")
        month = row.get("MONTH")
        if not year or not month:
            continue

        lat = _safe_coordinate(row.get("LATITUDE"))
        lon = _safe_coordinate(row.get("LONGITUD")) or _safe_coordinate(row.get("LONGITUDE"))

        records.append(
            FarsCrashRecord.model_validate(
                {
                    "case_id": int(row["ST_CASE"]),
                    "state_fips": state_fips,
                    "county_fips": county_fips,
                    "year": int(year),
                    "month": int(month),
                    "fatalities": fatals,
                    "persons": _safe_int(row.get("PERSONS")),
                    "pedestrians": _safe_int(row.get("PEDS")),
                    "drunk_drivers": _safe_int(row.get("DRUNK_DR")),
                    "latitude": lat,
                    "longitude": lon,
                }
            )
        )
    return records


def extract_fars(
    settings: Settings,
    start_year: int = 2015,
    end_year: int = 2022,
    *,
    force: bool = False,
) -> pl.DataFrame:
    parquet_dir = settings.staging_dir / "fars"
    parquet_path = parquet_dir / f"fars_dfw_{start_year}_{end_year}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    state_code = int(DFW_STATE_FIPS)
    county_codes = {name: int(fips) for name, fips in DFW_COUNTY_FIPS.items()}

    all_raw: list[dict] = []
    requests = [
        (year, name, code)
        for year in range(start_year, end_year + 1)
        for name, code in county_codes.items()
    ]
    for i, (year, county_name, county_code) in enumerate(requests):
        if i > 0:
            time.sleep(1.0)

        rows = _fetch_county_year(state_code, county_code, year)
        logger.info(
            "FARS %d %s (county %03d): %d crashes",
            year,
            county_name,
            county_code,
            len(rows),
        )
        all_raw.extend(rows)

    raw_dir = settings.raw_dir / "fars"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"fars_dfw_{start_year}_{end_year}.json"
    raw_path.write_text(json.dumps(all_raw, indent=2))

    records = _to_records(all_raw, DFW_STATE_FIPS)
    row_dicts = [r.model_dump() for r in records]
    df = pl.DataFrame(row_dicts)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
