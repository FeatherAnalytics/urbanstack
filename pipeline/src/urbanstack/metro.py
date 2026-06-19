from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetroConfig:
    metro_id: str
    metro_name: str
    metro_fips: str
    state_fips: str
    state_abbr: str
    counties: dict[str, str]
    center: tuple[float, float]
    zoom: int
    transit_agencies: dict[str, str]
    gtfs_feeds: dict[str, str]
    umr_names: list[str] = field(default_factory=list)

    @property
    def state_fips_int(self) -> int:
        return int(self.state_fips)

    @property
    def county_fips_set(self) -> set[str]:
        return set(self.counties.values())

    @property
    def county_fips_5_set(self) -> set[str]:
        return {f"{self.state_fips}{fips}" for fips in self.counties.values()}

    # yagni: single-state only — add additional_states: dict[str, dict[str, str]] for multi-state metros (Chicago IL-IN-WI, NYC NY-NJ-CT)


DFW = MetroConfig(
    metro_id="dfw",
    metro_name="Dallas-Fort Worth-Arlington MSA",
    metro_fips="19100",
    state_fips="48",
    state_abbr="TX",
    counties={
        "Collin": "085",
        "Dallas": "113",
        "Denton": "121",
        "Ellis": "139",
        "Hood": "221",
        "Hunt": "231",
        "Johnson": "251",
        "Kaufman": "257",
        "Parker": "367",
        "Rockwall": "397",
        "Tarrant": "439",
        "Wise": "497",
    },
    center=(32.78, -96.85),
    zoom=8,
    transit_agencies={
        "60056": "Dallas Area Rapid Transit",
        "60007": "Fort Worth Transportation Authority",
        "60101": "Denton County Transportation Authority",
    },
    gtfs_feeds={
        "DART": "https://www.dart.org/transitdata/latest/google_transit.zip",
        "Trinity Metro": "http://sched.ridetm.org/gtfs/fwtatransitdata.zip",
        "DCTA": "https://gtfs.remix.com/dcta_denton_tx_us.zip",
    },
    umr_names=[
        "Dallas-Fort Worth-Arlington",
        "Dallas-Fort Worth-Arlington TX",
        "Dallas-Fort Worth-Arlington, TX",
    ],
)

CHICAGO = MetroConfig(
    metro_id="chicago",
    metro_name="Chicago-Naperville-Elgin MSA",
    metro_fips="16980",
    state_fips="17",
    state_abbr="IL",
    counties={
        "Cook": "031",
        "DuPage": "043",
        "Kane": "089",
        "Kendall": "093",
        "Lake": "097",
        "McHenry": "111",
        "Will": "197",
    },
    center=(41.88, -87.63),
    zoom=8,
    transit_agencies={
        "50066": "Chicago Transit Authority",
        "50064": "Metra",
        "50065": "Pace",
    },
    gtfs_feeds={
        "CTA": "https://www.transitchicago.com/downloads/sch_data/google_transit.zip",
        "Metra": "https://schedule.metrarail.com/gtfs/schedule/feed.zip",
        "Pace": "https://www.pacebus.com/sites/default/files/GTFS/google_transit.zip",
    },
    umr_names=[
        "Chicago-Naperville",
        "Chicago-Naperville IL-IN-WI",
        "Chicago-Naperville, IL-IN-WI",
    ],
)

METRO_REGISTRY: dict[str, MetroConfig] = {
    "dfw": DFW,
    "chicago": CHICAGO,
}


def get_metro(metro_id: str) -> MetroConfig:
    if metro_id not in METRO_REGISTRY:
        available = sorted(METRO_REGISTRY.keys())
        raise KeyError(f"Unknown metro '{metro_id}'. Available: {available}")
    return METRO_REGISTRY[metro_id]
