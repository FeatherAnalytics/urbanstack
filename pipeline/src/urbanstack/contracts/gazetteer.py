from pydantic import BaseModel, Field


class GazetteerRecord(BaseModel):
    """Contract for Census Gazetteer county land/water area and centroid."""

    county_fips: str = Field(min_length=5, max_length=5)
    county_name: str
    state_abbr: str = Field(min_length=2, max_length=2)
    land_area_sqm: int = Field(ge=0)
    water_area_sqm: int = Field(ge=0)
    latitude: float
    longitude: float
