from dataclasses import dataclass, field

FIPS_TO_ABBR: dict[str, str] = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}


@dataclass(frozen=True)
class RegionMeta:
    region_name: str
    center: tuple[float, float]
    zoom: int


@dataclass(frozen=True)
class MetroConfig:
    metro_id: str
    metro_name: str
    metro_fips: str
    states: dict[str, dict[str, str]]
    center: tuple[float, float]
    zoom: int
    bounds: tuple[float, float, float, float]  # (min_lat, max_lat, min_lon, max_lon)
    transit_agencies: dict[str, str]
    umr_names: list[str] = field(default_factory=list)
    region: str = ""

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
    bounds=(32.25, 33.45, -97.60, -96.00),
    transit_agencies={
        "60056": "Dallas Area Rapid Transit",
        "60007": "Fort Worth Transportation Authority",
        "60101": "Denton County Transportation Authority",
    },
    umr_names=[
        "Dallas-Fort Worth-Arlington",
        "Dallas-Fort Worth-Arlington TX",
        "Dallas-Fort Worth-Arlington, TX",
    ],
    region="texas",
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
    bounds=(40.80, 42.50, -88.70, -87.20),
    transit_agencies={
        "50066": "Chicago Transit Authority",
        "50064": "Metra",
        "50065": "Pace",
    },
    umr_names=[
        "Chicago IL-IN",
        "Chicago-Naperville",
        "Chicago-Naperville IL-IN-WI",
    ],
    region="midwest",
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
    bounds=(40.10, 41.60, -74.90, -73.30),
    transit_agencies={
        "20008": "MTA New York City Transit",
        "20188": "NJ Transit",
        "20171": "Port Authority Trans-Hudson",
    },
    umr_names=[
        "New York-Newark NY-NJ-CT",
        "New York-Newark",
    ],
    region="northeast",
)

HOUSTON = MetroConfig(
    metro_id="houston",
    metro_name="Houston-Pasadena-The Woodlands MSA",
    metro_fips="26420",
    states={
        "48": {
            "Austin": "015",
            "Brazoria": "039",
            "Chambers": "071",
            "Fort Bend": "157",
            "Galveston": "167",
            "Harris": "201",
            "Liberty": "291",
            "Montgomery": "339",
            "San Jacinto": "407",
            "Waller": "473",
        },
    },
    center=(29.76, -95.37),
    zoom=8,
    bounds=(28.90, 30.60, -96.10, -94.30),
    transit_agencies={
        "60008": "Metropolitan Transit Authority of Harris County",
        "60108": "Harris County Transit",
    },
    umr_names=[
        "Houston TX",
    ],
    region="texas",
)

AUSTIN = MetroConfig(
    metro_id="austin",
    metro_name="Austin-Round Rock-San Marcos MSA",
    metro_fips="12420",
    states={
        "48": {
            "Bastrop": "021",
            "Caldwell": "055",
            "Hays": "209",
            "Travis": "453",
            "Williamson": "491",
        },
    },
    center=(30.27, -97.74),
    zoom=9,
    bounds=(29.70, 30.90, -98.20, -97.00),
    transit_agencies={
        "60048": "Capital Metropolitan Transportation Authority",
    },
    umr_names=[
        "Austin TX",
    ],
    region="texas",
)

SAN_ANTONIO = MetroConfig(
    metro_id="san_antonio",
    metro_name="San Antonio-New Braunfels MSA",
    metro_fips="41700",
    states={
        "48": {
            "Atascosa": "013",
            "Bandera": "019",
            "Bexar": "029",
            "Comal": "091",
            "Guadalupe": "187",
            "Kendall": "259",
            "Medina": "325",
            "Wilson": "493",
        },
    },
    center=(29.42, -98.49),
    zoom=9,
    bounds=(28.70, 30.00, -99.50, -97.60),
    transit_agencies={
        "60011": "VIA Metropolitan Transit",
    },
    umr_names=[
        "San Antonio TX",
    ],
    region="texas",
)

BOSTON = MetroConfig(
    metro_id="boston",
    metro_name="Boston-Cambridge-Newton MSA",
    metro_fips="14460",
    states={
        "25": {
            "Essex": "009",
            "Middlesex": "017",
            "Norfolk": "021",
            "Plymouth": "023",
            "Suffolk": "025",
        },
        "33": {
            "Rockingham": "015",
            "Strafford": "017",
        },
    },
    center=(42.36, -71.06),
    zoom=8,
    bounds=(41.70, 43.20, -71.90, -70.40),
    transit_agencies={
        "10003": "Massachusetts Bay Transportation Authority",
    },
    umr_names=[
        "Boston MA-NH-RI",
    ],
    region="northeast",
)

DENVER = MetroConfig(
    metro_id="denver",
    metro_name="Denver-Aurora-Centennial MSA",
    metro_fips="19740",
    states={
        "08": {
            "Adams": "001",
            "Arapahoe": "005",
            "Broomfield": "014",
            "Clear Creek": "019",
            "Denver": "031",
            "Douglas": "035",
            "Elbert": "039",
            "Gilpin": "047",
            "Jefferson": "059",
            "Park": "093",
        },
    },
    center=(39.74, -104.99),
    zoom=8,
    # Tight around the RTD service area: excludes Fort Collins (Transfort, ~40.4)
    # and Colorado Springs (Mountain Metro, ~38.8) so GTFS discovery only catches RTD.
    bounds=(39.20, 40.15, -105.45, -104.40),
    transit_agencies={
        "80006": "Regional Transportation District",
    },
    umr_names=[
        "Denver-Aurora CO",
        "Denver-Aurora",
        "Denver-Aurora, CO",
    ],
    region="mountain",
)

MSP = MetroConfig(
    metro_id="msp",
    metro_name="Minneapolis-St. Paul-Bloomington MSA",
    metro_fips="33460",
    states={
        "27": {
            "Anoka": "003",
            "Carver": "019",
            "Chisago": "025",
            "Dakota": "037",
            "Hennepin": "053",
            "Isanti": "059",
            "Le Sueur": "079",
            "Mille Lacs": "095",
            "Ramsey": "123",
            "Scott": "139",
            "Sherburne": "141",
            "Washington": "163",
            "Wright": "171",
        },
        "55": {
            "Pierce": "093",
            "St. Croix": "109",
        },
    },
    center=(44.98, -93.27),
    zoom=8,
    bounds=(44.0, 46.2, -94.5, -92.0),
    transit_agencies={
        "50027": "Metro Transit",
    },
    umr_names=[
        "Minneapolis-St. Paul MN-WI",
        "Minneapolis-St Paul MN-WI",
    ],
    region="midwest",
)

PORTLAND = MetroConfig(
    metro_id="portland",
    metro_name="Portland-Vancouver-Hillsboro MSA",
    metro_fips="38900",
    states={
        "41": {
            "Clackamas": "005",
            "Columbia": "009",
            "Multnomah": "051",
            "Washington": "067",
            "Yamhill": "071",
        },
        "53": {
            "Clark": "011",
            "Skamania": "059",
        },
    },
    center=(45.52, -122.68),
    zoom=8,
    bounds=(45.0, 46.3, -123.5, -121.5),
    transit_agencies={
        "00008": "TriMet",
    },
    umr_names=[
        "Portland OR-WA",
        "Portland-Vancouver OR-WA",
    ],
    region="pacific_northwest",
)

CHEYENNE = MetroConfig(
    metro_id="cheyenne",
    metro_name="Cheyenne MSA",
    metro_fips="16940",
    states={
        "56": {
            "Laramie": "021",
        },
    },
    center=(41.14, -104.82),
    zoom=10,
    bounds=(40.80, 41.50, -105.20, -104.40),
    transit_agencies={
        "80020": "City of Cheyenne Transit Program",
    },
    umr_names=[
        "Cheyenne WY",
    ],
    region="mountain",
)

METRO_REGISTRY: dict[str, MetroConfig] = {
    "dfw": DFW,
    "chicago": CHICAGO,
    "nyc": NYC,
    "houston": HOUSTON,
    "austin": AUSTIN,
    "san_antonio": SAN_ANTONIO,
    "boston": BOSTON,
    "denver": DENVER,
    "cheyenne": CHEYENNE,
    "msp": MSP,
    "portland": PORTLAND,
}

REGION_CONFIGS: dict[str, RegionMeta] = {
    "texas": RegionMeta(region_name="Texas", center=(30.5, -97.0), zoom=6),
    "northeast": RegionMeta(region_name="Northeast", center=(41.5, -72.5), zoom=6),
    "midwest": RegionMeta(region_name="Midwest", center=(41.88, -87.63), zoom=7),
    "mountain": RegionMeta(region_name="Mountain", center=(40.44, -104.90), zoom=7),
    "pacific_northwest": RegionMeta(region_name="Pacific Northwest", center=(45.52, -122.68), zoom=7),
}


def get_metro(metro_id: str) -> MetroConfig:
    if metro_id not in METRO_REGISTRY:
        available = sorted(METRO_REGISTRY.keys())
        raise KeyError(f"Unknown metro '{metro_id}'. Available: {available}")
    return METRO_REGISTRY[metro_id]
