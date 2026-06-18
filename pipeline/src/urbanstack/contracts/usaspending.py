from pydantic import BaseModel, Field


class UsaspendingCountyRecord(BaseModel):
    """Contract for USAspending federal grant spending aggregated by county."""

    county_fips: str = Field(min_length=5, max_length=5)
    county_name: str
    total_obligation: float
    per_capita: float | None = None
    population: int | None = Field(default=None, ge=0)
    fiscal_year_start: str
    fiscal_year_end: str
