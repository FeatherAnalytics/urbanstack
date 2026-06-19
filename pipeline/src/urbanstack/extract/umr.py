import logging
from pathlib import Path

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.umr import UmrRecord

logger = logging.getLogger(__name__)

UMR_XLSX_URL = (
    "https://tti.tamu.edu/documents/umr/data/complete-data-2025-umr-by-tti.xlsx"
)

DFW_NAMES = [
    "Dallas-Fort Worth-Arlington",
    "Dallas-Fort Worth-Arlington TX",
    "Dallas-Fort Worth-Arlington, TX",
]

COLUMN_MAP: dict[str, str] = {
    "Travel Time Index": "travel_time_index",
    "Planning Time Index": "planning_time_index",
    "Freeway Planning Time Index": "planning_time_index",
    "Annual Delay per Auto Commuter (hours)": "annual_delay_per_commuter",
    "Congestion Cost per Auto Commuter (dollars)": "congestion_cost_per_commuter",
    "Total Delay (1,000 person-hours)": "total_delay_thousand_hours",
    "Annual Hours of Delay": "total_delay_thousand_hours",
    "Total Excess Fuel Consumed (1,000 gallons)": "total_excess_fuel_thousand_gallons",
    "Annual Excess Fuel Consumed": "total_excess_fuel_thousand_gallons",
}

OFFSET_COLUMNS: list[tuple[str, int, str]] = [
    ("Annual Hours of Delay", 2, "annual_delay_per_commuter"),
    ("Annual Congestion Cost", 2, "congestion_cost_per_commuter"),
]


def _try_download(settings: Settings) -> Path | None:
    """Attempt to download UMR Excel from TTI. Returns path or None on failure."""
    raw_dir = settings.raw_dir / "umr"
    raw_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = raw_dir / "complete-data-umr.xlsx"
    if xlsx_path.exists():
        return xlsx_path

    try:
        resp = requests.get(UMR_XLSX_URL, timeout=60)
        resp.raise_for_status()
        xlsx_path.write_bytes(resp.content)
        logger.info("Downloaded UMR data to %s", xlsx_path)
        return xlsx_path
    except (requests.RequestException, OSError) as exc:
        logger.warning("Could not download UMR data: %s", exc)
        return None


def _find_local_file(settings: Settings) -> Path | None:
    """Look for manually-placed UMR data in data/raw/umr/."""
    raw_dir = settings.raw_dir / "umr"
    if not raw_dir.exists():
        return None
    for ext in ("*.xlsx", "*.xls", "*.csv"):
        files = list(raw_dir.glob(ext))
        if files:
            return files[0]
    return None


def _load_raw(path: Path) -> pl.DataFrame:
    if path.suffix in (".xlsx", ".xls"):
        return pl.read_excel(path, engine="calamine")
    return pl.read_csv(path, infer_schema_length=10000)


def _normalize_columns(df: pl.DataFrame) -> dict[str, str]:
    """Build a rename map from actual columns to our standard names."""
    rename: dict[str, str] = {}
    columns = df.columns
    lower_cols = {c.strip().lower(): c for c in columns}

    for pattern, target in COLUMN_MAP.items():
        key = pattern.strip().lower()
        if key in lower_cols:
            rename[lower_cols[key]] = target

    col_index = {c.strip().lower(): i for i, c in enumerate(columns)}
    for parent_prefix, offset, target in OFFSET_COLUMNS:
        if target in rename.values():
            continue
        for lower_name, idx in col_index.items():
            if lower_name.startswith(parent_prefix.lower()):
                sub_idx = idx + offset
                if sub_idx < len(columns):
                    rename[columns[sub_idx]] = target
                break

    for candidate in ("Urban Area", "urban_area", "Urban Area Name", "Area"):
        key = candidate.strip().lower()
        if key in lower_cols:
            rename[lower_cols[key]] = "urban_area"
            break

    for candidate in ("Year", "year", "Data Year"):
        key = candidate.strip().lower()
        if key in lower_cols:
            rename[lower_cols[key]] = "year"
            break

    return rename


def _filter_dfw(df: pl.DataFrame) -> pl.DataFrame:
    """Filter to DFW metro rows."""
    if "urban_area" not in df.columns:
        return df
    urban_lower = pl.col("urban_area").str.to_lowercase().str.strip_chars()
    dfw_lower = [n.lower() for n in DFW_NAMES]
    return df.filter(urban_lower.is_in(dfw_lower))


def _to_records(df: pl.DataFrame) -> list[UmrRecord]:
    records: list[UmrRecord] = []
    for row in df.to_dicts():
        kwargs: dict[str, str | int | float | None] = {
            "urban_area": str(row.get("urban_area", "")),
            "year": int(row["year"]),
        }
        for field in (
            "travel_time_index",
            "planning_time_index",
            "annual_delay_per_commuter",
            "congestion_cost_per_commuter",
            "total_delay_thousand_hours",
            "total_excess_fuel_thousand_gallons",
        ):
            val = row.get(field)
            if val is not None:
                try:
                    fval = float(val)
                    kwargs[field] = fval if fval != 0.0 else None
                except (ValueError, TypeError):
                    kwargs[field] = None
            else:
                kwargs[field] = None
        records.append(UmrRecord.model_validate(kwargs))
    return records


def extract_umr(
    settings: Settings,
    *,
    force: bool = False,
) -> pl.DataFrame:
    parquet_dir = settings.staging_dir / "umr"
    parquet_path = parquet_dir / "umr_dfw.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    source_path = _try_download(settings)
    if source_path is None:
        source_path = _find_local_file(settings)

    if source_path is None:
        raise FileNotFoundError(
            "No UMR data found. Either place an Excel/CSV file in "
            f"{settings.raw_dir / 'umr'} or ensure network access to {UMR_XLSX_URL}"
        )

    logger.info("Reading UMR data from %s", source_path)
    raw_df = _load_raw(source_path)

    rename = _normalize_columns(raw_df)
    if not rename:
        raise ValueError(
            f"Could not map UMR columns. Found: {raw_df.columns}. "
            f"Expected patterns like: {list(COLUMN_MAP.keys())}"
        )

    df = raw_df.rename(rename)
    df = _filter_dfw(df)

    if len(df) == 0:
        raise ValueError(
            "No DFW rows found after filtering. "
            f"Searched for urban_area matching: {DFW_NAMES}"
        )

    records = _to_records(df)
    rows = [r.model_dump() for r in records]
    result = pl.DataFrame(rows)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    result.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(result), parquet_path)

    return result
