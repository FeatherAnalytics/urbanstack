import duckdb

from urbanstack.config import Settings


def load_marts(settings: Settings) -> duckdb.DuckDBPyConnection:
    db_path = settings.marts_dir / "urbanstack.duckdb"
    conn = duckdb.connect(str(db_path))

    try:
        for metro_dir in sorted(settings.marts_dir.iterdir()):
            if not metro_dir.is_dir() or metro_dir.name == "national":
                continue
            metro_id = metro_dir.name
            for parquet_file in sorted(metro_dir.glob("*.parquet")):
                table_name = f"{metro_id}__{parquet_file.stem}"
                conn.execute(
                    f'CREATE OR REPLACE TABLE "{table_name}" '
                    "AS SELECT * FROM read_parquet(?)",
                    [str(parquet_file)],
                )

        national_dir = settings.marts_dir / "national"
        if national_dir.exists():
            for parquet_file in sorted(national_dir.glob("*.parquet")):
                conn.execute(
                    f'CREATE OR REPLACE TABLE "{parquet_file.stem}" '
                    "AS SELECT * FROM read_parquet(?)",
                    [str(parquet_file)],
                )
    except Exception:
        conn.close()
        raise

    return conn
