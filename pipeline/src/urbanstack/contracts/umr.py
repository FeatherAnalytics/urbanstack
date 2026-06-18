from pydantic import BaseModel, Field


class UmrRecord(BaseModel):
    """Contract for Texas A&M Urban Mobility Report congestion metrics."""

    urban_area: str = Field(min_length=1)
    year: int = Field(ge=1982)
    travel_time_index: float | None = Field(default=None, ge=1.0)
    planning_time_index: float | None = Field(default=None, ge=1.0)
    annual_delay_per_commuter: float | None = Field(default=None, ge=0)
    congestion_cost_per_commuter: float | None = Field(default=None, ge=0)
    total_delay_thousand_hours: float | None = Field(default=None, ge=0)
    total_excess_fuel_thousand_gallons: float | None = Field(default=None, ge=0)
