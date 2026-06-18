import json
import logging
import time

import polars as pl

from urbanstack.config import Settings
from urbanstack.contracts.ntd import NtdRidershipRecord
from urbanstack.extract._socrata import fetch_socrata_pages

logger = logging.getLogger(__name__)

NTD_MONTHLY_URL = "https://data.transportation.gov/resource/8bui-9xvu.json"

DFW_TRANSIT_AGENCIES: dict[str, str] = {
    "60056": "Dallas Area Rapid Transit",
    "60086": "Trinity Metro",
    "60166": "Denton County Transportation Authority",
}


def _fetch_agency(ntd_id: str) -> list[dict[str, str]]:
    params = {
        "$where": f"ntd_id='{ntd_id}'",
        "$order": "date",
    }
    return fetch_socrata_pages(NTD_MONTHLY_URL, params)


def _to_records(raw_rows: list[dict[str, str]]) -> list[NtdRidershipRecord]:
    records: list[NtdRidershipRecord] = []
    for row in raw_rows:
        date_str = row.get("date", "")
        if not date_str:
            continue

        try:
            year = int(date_str[:4])
            month = int(date_str[5:7])
        except (ValueError, IndexError):
            continue

        upt = row.get("upt")
        vrm = row.get("vrm")
        vrh = row.get("vrh")

        records.append(
            NtdRidershipRecord.model_validate(
                {
                    "ntd_id": row["ntd_id"],
                    "agency_name": row.get("agency", ""),
                    "mode": row.get("mode", ""),
                    "year": year,
                    "month": month,
                    "unlinked_passenger_trips": int(upt) if upt else None,
                    "vehicle_revenue_miles": float(vrm) if vrm else None,
                    "vehicle_revenue_hours": float(vrh) if vrh else None,
                }
            )
        )
    return records


def extract_ntd(
    settings: Settings,
    *,
    force: bool = False,
) -> pl.DataFrame:
    parquet_dir = settings.staging_dir / "ntd"
    parquet_path = parquet_dir / "ntd_dfw.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    all_raw: list[dict[str, str]] = []
    for i, ntd_id in enumerate(DFW_TRANSIT_AGENCIES):
        if i > 0:
            time.sleep(0.5)
        rows = _fetch_agency(ntd_id)
        all_raw.extend(rows)

    raw_dir = settings.raw_dir / "ntd"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "ntd_dfw.json"
    raw_path.write_text(json.dumps(all_raw, indent=2))

    records = _to_records(all_raw)
    row_dicts = [r.model_dump() for r in records]
    df = pl.DataFrame(row_dicts)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
