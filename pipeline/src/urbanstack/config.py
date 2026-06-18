import os
from dataclasses import dataclass, field
from pathlib import Path

import truststore
from dotenv import find_dotenv, load_dotenv


@dataclass(frozen=True)
class Settings:
    census_api_key: str = ""
    data_dir: Path = field(default_factory=lambda: Path("data"))

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / "staging"

    @property
    def marts_dir(self) -> Path:
        return self.data_dir / "marts"

    def ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.staging_dir, self.marts_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    truststore.inject_into_ssl()
    load_dotenv(find_dotenv(usecwd=True))
    return Settings(
        census_api_key=os.environ.get("CENSUS_API_KEY", ""),
        data_dir=Path(os.environ.get("DATA_DIR", "data")),
    )
