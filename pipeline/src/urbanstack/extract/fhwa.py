import json
import logging
import time

import polars as pl

from urbanstack.config import Settings
from urbanstack.contracts.fhwa import FhwaVolumeRecord
from urbanstack.extract._socrata import fetch_socrata_pages
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)

TMAS_DATASET_IDS: dict[int, str] = {
    2015: "gjfe-peac",
    2016: "qjsn-7dw8",
    2017: "354n-8ysa",
    2018: "4z2n-nkpd",
    2019: "2hya-qc6x",
    2020: "ymmm-mwzp",
    2021: "9fns-puia",
    2022: "ytjj-yht4",
    2023: "kv7k-jsg5",
}

SOCRATA_BASE = "https://data.transportation.gov/resource/{dataset_id}.json"


def _dataset_url(year: int) -> str:
    dataset_id = TMAS_DATASET_IDS.get(year)
    if not dataset_id:
        available = sorted(TMAS_DATASET_IDS.keys())
        raise ValueError(f"No TMAS dataset for year {year}. Available: {available}")
    return SOCRATA_BASE.format(dataset_id=dataset_id)


def _fetch_month(url: str, state_fips: str, year: int, month: int) -> list[dict[str, str]]:
    """Fetch daily aggregated volumes for one state+month via Socrata.

    Fetches all Texas data (not just DFW counties) because the TMAS Socrata
    dataset has no county field. County association happens in the transform
    layer via station lat/lon spatial join.
    """
    params = {
        "$select": (
            "station_id, fsystem_cd, rural_urban, year, month, day, sum(veh_count) as daily_volume"
        ),
        "$where": f"state_cd='{state_fips}' AND month='{month}'",
        "$group": "station_id, fsystem_cd, rural_urban, year, month, day",
        "$order": "station_id, day",
    }
    return fetch_socrata_pages(url, params)


def _to_records(raw_rows: list[dict[str, str]], state_fips: str) -> list[FhwaVolumeRecord]:
    records: list[FhwaVolumeRecord] = []
    for row in raw_rows:
        vol = row.get("daily_volume")
        if vol is None:
            continue
        records.append(
            FhwaVolumeRecord.model_validate(
                {
                    "station_id": row["station_id"],
                    "state_fips": state_fips,
                    "functional_class": row.get("fsystem_cd"),
                    "rural_urban": row.get("rural_urban"),
                    "year": int(row["year"]),
                    "month": int(row["month"]),
                    "day": int(row["day"]),
                    "daily_volume": int(vol),
                }
            )
        )
    return records


def extract_fhwa(
    settings: Settings,
    metro: MetroConfig,
    year: int = 2023,
    *,
    force: bool = False,
) -> pl.DataFrame:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "fhwa"
    parquet_path = parquet_dir / f"fhwa_{metro.state_abbr.lower()}_{year}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    url = _dataset_url(year)

    all_raw: list[dict[str, str]] = []
    for month in range(1, 13):
        if month > 1:
            time.sleep(0.5)
        rows = _fetch_month(url, metro.state_fips, year, month)
        all_raw.extend(rows)

    raw_dir = settings.metro_raw_dir(metro.metro_id) / "fhwa"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"fhwa_{metro.state_abbr.lower()}_{year}.json"
    raw_path.write_text(json.dumps(all_raw, indent=2))

    records = _to_records(all_raw, metro.state_fips)
    rows = [r.model_dump() for r in records]
    df = pl.DataFrame(rows)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
