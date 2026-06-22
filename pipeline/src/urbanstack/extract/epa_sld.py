import logging
from pathlib import Path

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.epa_sld import SLD_COLUMN_MAP, EpaSldRecord
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)

SLD_URL = (
    "https://edg.epa.gov/EPADataCommons/public/OA/EPA_SmartLocationDatabase_V3_Jan_2021_Final.csv"
)

DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


def _download_csv(dest: Path, *, force: bool = False) -> None:
    if dest.exists() and not force:
        logger.info("Raw CSV exists, skipping download: %s", dest)
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading EPA SLD CSV (~170 MB) to %s", dest)

    resp = requests.get(SLD_URL, stream=True, timeout=300)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                logger.info("Download progress: %d%%", pct)

    logger.info("Download complete: %s (%d bytes)", dest, downloaded)


def _resolve_columns(csv_path: Path) -> dict[str, str]:
    """Read CSV header and build case-insensitive rename map."""
    sample = pl.scan_csv(csv_path).head(1).collect()
    if sample.is_empty():
        raise ValueError(f"Empty CSV: {csv_path}")
    header_cols = sample.columns

    upper_map = {k.upper(): v for k, v in SLD_COLUMN_MAP.items()}
    rename: dict[str, str] = {}
    for col in header_cols:
        mapped = upper_map.get(col.upper())
        if mapped and mapped not in rename.values():
            rename[col] = mapped
    return rename


def extract_epa_sld(
    settings: Settings, metro: MetroConfig, *, force: bool = False
) -> pl.DataFrame:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "epa_sld"
    parquet_path = parquet_dir / f"epa_sld_{metro.metro_id}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    csv_path = settings.raw_dir / "epa_sld" / "sld_v3.csv"
    _download_csv(csv_path, force=force)

    rename = _resolve_columns(csv_path)
    keep_cols = list(rename.keys())

    county_codes = metro.county_fips_set
    state_col = next(k for k, v in rename.items() if v == "state_fips")
    county_col = next(k for k, v in rename.items() if v == "county_fips")

    df = (
        pl.scan_csv(csv_path, infer_schema_length=1000)
        .select(keep_cols)
        .filter(
            (pl.col(state_col).cast(pl.Utf8).str.zfill(2) == metro.state_fips)
            & (pl.col(county_col).cast(pl.Utf8).str.zfill(3).is_in(county_codes))
        )
        .collect()
        .rename(rename)
    )

    state = pl.col("state_fips").cast(pl.Utf8).str.zfill(2)
    county = pl.col("county_fips").cast(pl.Utf8).str.zfill(3)
    tract = pl.col("tract_fips").cast(pl.Int64).cast(pl.Utf8).str.zfill(6)
    blkgrp = pl.col("blkgrp_fips").cast(pl.Int64).cast(pl.Utf8).str.zfill(1)

    df = df.with_columns(
        state.alias("state_fips"),
        county.alias("county_fips"),
        tract.alias("tract_fips"),
        blkgrp.alias("blkgrp_fips"),
        pl.col("cbsa").cast(pl.Int64).cast(pl.Utf8),
        (state + county + tract + blkgrp).alias("geoid"),
    )

    float_cols = [c for c in df.columns if df[c].dtype in (pl.Float64, pl.Float32)]
    df = df.with_columns(
        pl.when(pl.col(c) < -99998).then(None).otherwise(pl.col(c)).alias(c)
        for c in float_cols
    )

    records = df.to_dicts()
    for r in records:
        EpaSldRecord.model_validate(r)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d DFW block groups to %s", len(df), parquet_path)

    return df
