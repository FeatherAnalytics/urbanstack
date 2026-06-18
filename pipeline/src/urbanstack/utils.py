from pathlib import Path


def find_parquet(directory: Path) -> Path | None:
    """Return the first .parquet file in a directory, or None."""
    if not directory.exists():
        return None
    files = sorted(directory.glob("*.parquet"))
    return files[0] if files else None
