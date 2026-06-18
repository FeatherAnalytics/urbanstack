import duckdb

from urbanstack.config import Settings


def load_marts(settings: Settings) -> duckdb.DuckDBPyConnection:
    """Load all mart Parquets into a DuckDB database. Returns connection."""
    db_path = settings.marts_dir / "urbanstack.duckdb"
    conn = duckdb.connect(str(db_path))

    try:
        for parquet_file in sorted(settings.marts_dir.glob("*.parquet")):
            table_name = parquet_file.stem
            conn.execute(
                f'CREATE OR REPLACE TABLE "{table_name}" '
                "AS SELECT * FROM read_parquet(?)",
                [str(parquet_file)],
            )
    except Exception:
        conn.close()
        raise

    return conn
