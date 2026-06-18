from pathlib import Path

from urbanstack.config import Settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.data_dir == Path("data")
    assert s.census_api_key == ""


def test_settings_dir_properties(tmp_data_dir: Path) -> None:
    s = Settings(data_dir=tmp_data_dir)
    assert s.raw_dir == tmp_data_dir / "raw"
    assert s.staging_dir == tmp_data_dir / "staging"
    assert s.marts_dir == tmp_data_dir / "marts"


def test_settings_ensure_dirs(tmp_path: Path) -> None:
    data_dir = tmp_path / "new_data"
    s = Settings(data_dir=data_dir)
    s.ensure_dirs()
    assert s.raw_dir.exists()
    assert s.staging_dir.exists()
    assert s.marts_dir.exists()
