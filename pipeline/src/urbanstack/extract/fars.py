import csv
import io
import logging
import zipfile
from pathlib import Path

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.fars import FarsCrashRecord
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)

FARS_ZIP_URL = "https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/FARS{year}NationalCSV.zip"


def _download_year_zip(year: int, raw_dir: Path, *, force: bool = False) -> bytes:
    zip_path = raw_dir / f"FARS{year}NationalCSV.zip"
    if zip_path.exists() and not force:
        logger.info("Using cached ZIP: %s", zip_path)
        return zip_path.read_bytes()

    url = FARS_ZIP_URL.format(year=year)
    logger.info("Downloading FARS %d from %s", year, url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()

    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(resp.content)
    return resp.content


def _read_accident_csv(zip_bytes: bytes) -> list[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        accident_name = next(
            (n for n in zf.namelist() if n.upper().endswith("ACCIDENT.CSV")),
            None,
        )
        if accident_name is None:
            msg = f"ACCIDENT.CSV not found in ZIP; contents: {zf.namelist()}"
            raise FileNotFoundError(msg)

        with zf.open(accident_name) as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")
            reader = csv.DictReader(text)
            return list(reader)


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_coordinate(val: object) -> float | None:
    """FARS uses 0.0, 77.7777, 88.8888, 99.9999 as sentinel values for unknown coordinates."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f not in (0.0, 99.9999, 77.7777, 88.8888) else None
    except (ValueError, TypeError):
        return None


def _to_records(
    raw_rows: list[dict],
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

        state_raw = row.get("STATE")
        if state_raw is None:
            continue
        state_fips = str(int(state_raw)).zfill(2)

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
    metro: MetroConfig,
    start_year: int = 2015,
    end_year: int = 2022,
    *,
    force: bool = False,
) -> pl.DataFrame:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "fars"
    parquet_path = parquet_dir / f"fars_{metro.metro_id}_{start_year}_{end_year}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    metro_filter: set[tuple[int, int]] = set()
    for state_fips, counties in metro.states.items():
        state_int = int(state_fips)
        for county_fips in counties.values():
            metro_filter.add((state_int, int(county_fips)))

    raw_dir = settings.raw_dir / "fars"

    all_raw: list[dict] = []
    for year in range(start_year, end_year + 1):
        zip_bytes = _download_year_zip(year, raw_dir, force=force)
        rows = _read_accident_csv(zip_bytes)

        metro_rows = [
            r for r in rows
            if (_safe_int(r.get("STATE")), _safe_int(r.get("COUNTY"))) in metro_filter
        ]
        logger.info(
            "FARS %d: %d total crashes, %d in %s",
            year, len(rows), len(metro_rows), metro.metro_id
        )
        all_raw.extend(metro_rows)

    records = _to_records(all_raw)
    row_dicts = [r.model_dump() for r in records]
    df = pl.DataFrame(row_dicts)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
