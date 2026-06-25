import polars as pl
from pydantic import BaseModel, Field


class OsmParkRecord(BaseModel):
    """Contract for OpenStreetMap park/green space polygons."""

    osm_id: int
    name: str | None = None
    park_type: str = Field(min_length=1)
    area_sqm: float = Field(ge=0)
    centroid_lat: float = Field(ge=-90, le=90)
    centroid_lon: float = Field(ge=-180, le=180)


OSM_PARK_SCHEMA: dict[str, type[pl.DataType]] = {
    "osm_id": pl.Int64,
    "name": pl.Utf8,
    "park_type": pl.Utf8,
    "area_sqm": pl.Float64,
    "centroid_lat": pl.Float64,
    "centroid_lon": pl.Float64,
}

PARK_TAGS: list[tuple[str, str]] = [
    ("leisure", "park"),
    ("leisure", "garden"),
    ("leisure", "playground"),
    ("landuse", "recreation_ground"),
]
