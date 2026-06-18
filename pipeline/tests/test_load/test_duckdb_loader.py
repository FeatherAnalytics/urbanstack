import polars as pl

from urbanstack.config import Settings
from urbanstack.load.duckdb_loader import load_marts


def test_load_marts_creates_table(settings: Settings) -> None:
    df = pl.DataFrame({"county_fips": ["48113"], "population": [100_000]})
    df.write_parquet(settings.marts_dir / "county_summary.parquet")

    conn = load_marts(settings)
    result = conn.execute("SELECT * FROM county_summary").fetchall()
    conn.close()

    assert len(result) == 1
    assert result[0] == ("48113", 100_000)


def test_multiple_parquets_create_multiple_tables(settings: Settings) -> None:
    pl.DataFrame({"a": [1]}).write_parquet(settings.marts_dir / "alpha.parquet")
    pl.DataFrame({"b": [2]}).write_parquet(settings.marts_dir / "beta.parquet")

    conn = load_marts(settings)
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = sorted(row[0] for row in tables)
    conn.close()

    assert table_names == ["alpha", "beta"]


def test_empty_marts_dir(settings: Settings) -> None:
    conn = load_marts(settings)
    tables = conn.execute("SHOW TABLES").fetchall()
    conn.close()

    assert tables == []


def test_load_marts_is_idempotent(settings: Settings) -> None:
    df = pl.DataFrame({"x": [1, 2, 3]})
    df.write_parquet(settings.marts_dir / "demo.parquet")

    load_marts(settings).close()
    conn = load_marts(settings)
    result = conn.execute("SELECT count(*) FROM demo").fetchone()
    conn.close()

    assert result == (3,)
