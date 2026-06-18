from pydantic import BaseModel, Field


class EpaSldRecord(BaseModel):
    """Contract for EPA Smart Location Database v3 at block group level."""

    geoid: str = Field(min_length=12, max_length=12)
    state_fips: str = Field(min_length=2, max_length=2)
    county_fips: str = Field(min_length=3, max_length=3)
    tract_fips: str
    cbsa: str

    # Density (D1)
    d1a: float | None = None  # gross housing unit density
    d1b: float | None = None  # gross population density
    d1c: float | None = None  # gross employment density

    # Diversity (D2)
    d2a_jphh: float | None = None  # jobs per household
    d2b_e8mixa: float | None = None  # 8-tier employment entropy

    # Design (D3)
    d3b: float | None = None  # street intersection density

    # Destination Accessibility (D5)
    d5dr: float | None = None  # regional destination accessibility (auto)
    d5de: float | None = None  # destination accessibility (employment)

    # Transit (D4)
    d4a: float | None = None  # distance to nearest transit stop (meters)
    d4d: float | None = None  # aggregate frequency of transit service

    # Walkability
    nat_walk_ind: float | None = None  # National Walkability Index (1-20)

    # Auto dependency
    pct_ao0: float | None = None  # % zero-car households
    autoown: float | None = None  # avg vehicles per household


SLD_COLUMN_MAP: dict[str, str] = {
    "GEOID10": "geoid",
    "GEOID20": "geoid",
    "STATEFP": "state_fips",
    "COUNTYFP": "county_fips",
    "TRACTCE": "tract_fips",
    "CBSA": "cbsa",
    "D1A": "d1a",
    "D1B": "d1b",
    "D1C": "d1c",
    "D2A_JPHH": "d2a_jphh",
    "D2B_E8MIXA": "d2b_e8mixa",
    "D3B": "d3b",
    "D5DR": "d5dr",
    "D5DE": "d5de",
    "D4A": "d4a",
    "D4D": "d4d",
    "NatWalkInd": "nat_walk_ind",
    "Pct_AO0": "pct_ao0",
    "AutoOwn": "autoown",
}
