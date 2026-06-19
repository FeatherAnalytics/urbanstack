import io
import logging
import zipfile
from pathlib import Path

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.contracts.gazetteer import GazetteerRecord
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_Gaz_counties_national.zip"
)


def _download(dest: Path, *, force: bool = False) -> None:
    if dest.exists() and not force:
        logger.info("Raw file exists, skipping download: %s", dest)
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading Gazetteer counties to %s", dest)

    resp = requests.get(GAZETTEER_URL, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
        if not txt_names:
            raise ValueError(f"No .txt file found in Gazetteer ZIP: {zf.namelist()}")
        dest.write_bytes(zf.read(txt_names[0]))
    logger.info("Download complete: %s (%d bytes)", dest, len(resp.content))


def _parse(raw_path: Path, metro: MetroConfig) -> list[GazetteerRecord]:
    df = pl.read_csv(raw_path, separator="\t", infer_schema_length=0)
    df = df.rename({c: c.strip() for c in df.columns})

    df = df.filter(pl.col("GEOID").str.strip_chars().is_in(metro.county_fips_5_set))

    records: list[GazetteerRecord] = []
    for row in df.to_dicts():
        records.append(
            GazetteerRecord.model_validate(
                {
                    "county_fips": row["GEOID"].strip(),
                    "county_name": row["NAME"].strip(),
                    "state_abbr": row["USPS"].strip(),
                    "land_area_sqm": int(row["ALAND"].strip()),
                    "water_area_sqm": int(row["AWATER"].strip()),
                    "latitude": float(row["INTPTLAT"].strip()),
                    "longitude": float(row["INTPTLONG"].strip()),
                }
            )
        )
    return records


def extract_gazetteer(settings: Settings, metro: MetroConfig, *, force: bool = False) -> pl.DataFrame:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "gazetteer"
    parquet_path = parquet_dir / f"gazetteer_{metro.metro_id}.parquet"

    if parquet_path.exists() and not force:
        logger.info("Parquet exists, skipping: %s", parquet_path)
        return pl.read_parquet(parquet_path)

    raw_path = settings.raw_dir / "gazetteer" / "2024_Gaz_counties_national.txt"
    _download(raw_path, force=force)

    records = _parse(raw_path, metro)
    row_dicts = [r.model_dump() for r in records]
    df = pl.DataFrame(row_dicts)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_path)
    logger.info("Wrote %d rows to %s", len(df), parquet_path)

    return df
