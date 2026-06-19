import polars as pl

from urbanstack.config import Settings
from urbanstack.load.duckdb_loader import load_marts


def test_load_marts_creates_table(settings: Settings) -> None:
    metro_dir = settings.marts_dir / "dfw"
    metro_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame({"county_fips": ["48113"], "population": [100_000]})
    df.write_parquet(metro_dir / "county_summary.parquet")

    conn = load_marts(settings)
    result = conn.execute('SELECT * FROM "dfw__county_summary"').fetchall()
    conn.close()

    assert len(result) == 1
    assert result[0] == ("48113", 100_000)


def test_multiple_metros_create_namespaced_tables(settings: Settings) -> None:
    dfw_dir = settings.marts_dir / "dfw"
    dfw_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"a": [1]}).write_parquet(dfw_dir / "county_summary.parquet")

    chi_dir = settings.marts_dir / "chicago"
    chi_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"a": [2]}).write_parquet(chi_dir / "county_summary.parquet")

    conn = load_marts(settings)
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = sorted(row[0] for row in tables)
    conn.close()

    assert table_names == ["chicago__county_summary", "dfw__county_summary"]


def test_national_tables_use_plain_names(settings: Settings) -> None:
    national_dir = settings.marts_dir / "national"
    national_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"metro_id": ["dfw"]}).write_parquet(national_dir / "metro_summary.parquet")

    conn = load_marts(settings)
    result = conn.execute("SELECT * FROM metro_summary").fetchall()
    conn.close()

    assert len(result) == 1


def test_empty_marts_dir(settings: Settings) -> None:
    conn = load_marts(settings)
    tables = conn.execute("SHOW TABLES").fetchall()
    conn.close()

    assert tables == []


def test_load_marts_is_idempotent(settings: Settings) -> None:
    metro_dir = settings.marts_dir / "dfw"
    metro_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame({"x": [1, 2, 3]})
    df.write_parquet(metro_dir / "demo.parquet")

    load_marts(settings).close()
    conn = load_marts(settings)
    result = conn.execute('SELECT count(*) FROM "dfw__demo"').fetchone()
    conn.close()

    assert result == (3,)
