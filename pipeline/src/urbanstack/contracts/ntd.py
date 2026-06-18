from pydantic import BaseModel, Field


class NtdRidershipRecord(BaseModel):
    """Contract for NTD monthly ridership at agency+mode level."""

    ntd_id: str = Field(min_length=1)
    agency_name: str
    mode: str  # e.g., "HR" (heavy rail), "MB" (bus), "LR" (light rail), "DR" (demand response)
    year: int = Field(ge=2000)
    month: int = Field(ge=1, le=12)
    unlinked_passenger_trips: int | None = Field(default=None, ge=0)
    vehicle_revenue_miles: float | None = Field(default=None, ge=0)
    vehicle_revenue_hours: float | None = Field(default=None, ge=0)
