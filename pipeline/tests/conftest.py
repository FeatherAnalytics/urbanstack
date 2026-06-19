from pathlib import Path

import pytest

from urbanstack.config import Settings
from urbanstack.metro import DFW, MetroConfig


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    for subdir in ("raw", "staging", "marts"):
        (tmp_path / subdir).mkdir()
    return tmp_path


@pytest.fixture
def settings(tmp_data_dir: Path) -> Settings:
    return Settings(census_api_key="test-key", data_dir=tmp_data_dir)


@pytest.fixture
def metro() -> MetroConfig:
    return DFW
