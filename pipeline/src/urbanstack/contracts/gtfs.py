from pydantic import BaseModel, Field


class GtfsRoute(BaseModel):
    """Contract for a GTFS transit route."""

    agency: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    route_short_name: str = ""
    route_long_name: str = ""
    route_type: int = Field(ge=0, le=12)
    route_color: str = ""


class GtfsStop(BaseModel):
    """Contract for a GTFS transit stop."""

    agency: str = Field(min_length=1)
    stop_id: str = Field(min_length=1)
    stop_name: str = ""
    latitude: float = Field(ge=24.0, le=50.0)
    longitude: float = Field(ge=-125.0, le=-65.0)


class GtfsShape(BaseModel):
    """Contract for a GTFS shape point (route geometry)."""

    agency: str = Field(min_length=1)
    shape_id: str = Field(min_length=1)
    latitude: float = Field(ge=24.0, le=50.0)
    longitude: float = Field(ge=-125.0, le=-65.0)
    sequence: int = Field(ge=0)
