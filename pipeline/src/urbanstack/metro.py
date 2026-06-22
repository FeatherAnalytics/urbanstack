from dataclasses import dataclass, field

FIPS_TO_ABBR: dict[str, str] = {
    "09": "CT",
    "17": "IL",
    "18": "IN",
    "34": "NJ",
    "36": "NY",
    "42": "PA",
    "48": "TX",
    "55": "WI",
}


@dataclass(frozen=True)
class MetroConfig:
    metro_id: str
    metro_name: str
    metro_fips: str
    states: dict[str, dict[str, str]]
    center: tuple[float, float]
    zoom: int
    transit_agencies: dict[str, str]
    gtfs_feeds: dict[str, str]
    umr_names: list[str] = field(default_factory=list)

    @property
    def state_fips_set(self) -> set[str]:
        return set(self.states.keys())

    @property
    def state_fips_int_set(self) -> set[int]:
        return {int(s) for s in self.states}

    @property
    def county_fips_5_set(self) -> set[str]:
        return {
            f"{state}{fips}"
            for state, counties in self.states.items()
            for fips in counties.values()
        }


DFW = MetroConfig(
    metro_id="dfw",
    metro_name="Dallas-Fort Worth-Arlington MSA",
    metro_fips="19100",
    states={
        "48": {
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
    states={
        "17": {
            "Cook": "031",
            "DeKalb": "037",
            "DuPage": "043",
            "Grundy": "063",
            "Kane": "089",
            "Kendall": "093",
            "Lake": "097",
            "McHenry": "111",
            "Will": "197",
        },
        "18": {
            "Jasper": "073",
            "Lake": "089",
            "Newton": "111",
            "Porter": "127",
        },
        "55": {
            "Kenosha": "059",
        },
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
        "Chicago IL-IN",
        "Chicago-Naperville",
        "Chicago-Naperville IL-IN-WI",
    ],
)

# yagni: CT counties omitted — 2020 Census redesigned CT
# into planning regions, complicating FIPS matching
NYC = MetroConfig(
    metro_id="nyc",
    metro_name="New York-Newark-Jersey City MSA",
    metro_fips="35620",
    states={
        "36": {
            "New York": "061",
            "Kings": "047",
            "Queens": "081",
            "Bronx": "005",
            "Richmond": "085",
            "Westchester": "119",
            "Rockland": "087",
            "Putnam": "079",
            "Orange": "071",
            "Dutchess": "027",
            "Suffolk": "103",
            "Nassau": "059",
        },
        "34": {
            "Bergen": "003",
            "Essex": "013",
            "Hudson": "017",
            "Hunterdon": "019",
            "Middlesex": "023",
            "Monmouth": "025",
            "Morris": "027",
            "Ocean": "029",
            "Passaic": "031",
            "Somerset": "035",
            "Sussex": "037",
            "Union": "039",
        },
        "42": {
            "Pike": "103",
        },
    },
    center=(40.71, -74.00),
    zoom=8,
    transit_agencies={
        "20008": "MTA New York City Transit",
        "20188": "NJ Transit",
        "20171": "Port Authority Trans-Hudson",
    },
    gtfs_feeds={
        "MTA": "http://web.mta.info/developers/data/nyct/subway/google_transit.zip",
    },
    umr_names=[
        "New York-Newark NY-NJ-CT",
        "New York-Newark",
    ],
)

METRO_REGISTRY: dict[str, MetroConfig] = {
    "dfw": DFW,
    "chicago": CHICAGO,
    "nyc": NYC,
}


def get_metro(metro_id: str) -> MetroConfig:
    if metro_id not in METRO_REGISTRY:
        available = sorted(METRO_REGISTRY.keys())
        raise KeyError(f"Unknown metro '{metro_id}'. Available: {available}")
    return METRO_REGISTRY[metro_id]
