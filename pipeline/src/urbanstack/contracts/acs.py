from typing import Literal

from pydantic import BaseModel, Field

Granularity = Literal["county", "block_group"]


class AcsRecord(BaseModel):
    """Contract for Census ACS data at county or block group level."""

    state_fips: str = Field(min_length=2, max_length=2)
    county_fips: str = Field(min_length=3, max_length=3)
    name: str
    tract_fips: str | None = Field(default=None, min_length=6, max_length=6)
    block_group_fips: str | None = Field(default=None, min_length=1, max_length=1)
    total_population: int | None = Field(default=None, ge=0)
    per_capita_income: int | None = Field(default=None, ge=0)
    median_household_income: int | None = Field(default=None, ge=0)
    commute_drove_alone: int | None = Field(default=None, ge=0)
    commute_transit: int | None = Field(default=None, ge=0)
    commute_walked: int | None = Field(default=None, ge=0)
    commute_biked: int | None = Field(default=None, ge=0)
    commute_wfh: int | None = Field(default=None, ge=0)
    vehicles_available: int | None = Field(default=None, ge=0)
    median_rent: int | None = Field(default=None, ge=0)
    median_home_value: int | None = Field(default=None, ge=0)

    @property
    def fips(self) -> str:
        base = f"{self.state_fips}{self.county_fips}"
        if self.tract_fips:
            base = f"{base}{self.tract_fips}"
        if self.block_group_fips:
            base = f"{base}{self.block_group_fips}"
        return base
