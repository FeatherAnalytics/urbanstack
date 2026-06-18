from pydantic import BaseModel, Field


class FarsCrashRecord(BaseModel):
    """Contract for NHTSA FARS fatal crash at accident level."""

    case_id: int
    state_fips: str = Field(min_length=2, max_length=2)
    county_fips: str = Field(min_length=3, max_length=3)
    year: int = Field(ge=2010)
    month: int = Field(ge=1, le=12)
    fatalities: int = Field(ge=1)
    persons: int | None = Field(default=None, ge=0)
    pedestrians: int | None = Field(default=None, ge=0)
    drunk_drivers: int | None = Field(default=None, ge=0)
    latitude: float | None = None
    longitude: float | None = None
