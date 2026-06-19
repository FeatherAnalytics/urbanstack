from pydantic import BaseModel, Field


class TmasStationRecord(BaseModel):
    """Contract for TMAS station with county assignment via spatial join."""

    station_id: str = Field(min_length=1)
    county_fips: str = Field(min_length=5, max_length=5)
    latitude: float
    longitude: float
    functional_class: str | None = None
