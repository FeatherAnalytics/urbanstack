from pydantic import BaseModel, Field


class FhwaVolumeRecord(BaseModel):
    """Contract for FHWA TMAS daily traffic volume at station level."""

    station_id: str = Field(min_length=1)
    state_fips: str = Field(min_length=2, max_length=2)
    functional_class: str | None = None
    rural_urban: str | None = None
    year: int = Field(ge=2015)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    daily_volume: int = Field(ge=0)
