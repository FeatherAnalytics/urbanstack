export interface CountyData {
  county_fips: string;
  county_name: string;
  population: number | null;
  per_capita_income: number | null;
  median_household_income: number | null;
  median_rent: number | null;
  median_home_value: number | null;
  pct_drove_alone: number | null;
  pct_transit: number | null;
  pct_walked: number | null;
  pct_biked: number | null;
  pct_wfh: number | null;
  avg_walkability: number | null;
  avg_transit_frequency: number | null;
  pct_zero_car_hh: number | null;
  total_fatalities: number | null;
  total_crashes: number | null;
  pedestrian_involved_crashes: number | null;
  drunk_driver_crashes: number | null;
  federal_obligation: number | null;
  federal_per_capita: number | null;
  pop_density_sqmi: number | null;
  travel_time_index: number | null;
  planning_time_index: number | null;
  annual_delay_hours: number | null;
  congestion_cost: number | null;
}

export type MetricKey = keyof Omit<CountyData, "county_fips" | "county_name">;

export type MetricCategory =
  | "Demographics"
  | "Transportation"
  | "Safety"
  | "Spending"
  | "Congestion";

export type MetricFormat = "number" | "currency" | "percent" | "decimal";

export interface MetricConfig {
  key: MetricKey;
  label: string;
  category: MetricCategory;
  format: MetricFormat;
  /** RGB color stops for interpolation: low, mid, high */
  colorScale: [number, number, number][];
  /** true when higher values = worse outcome (fatalities, crashes) */
  invertSentiment?: boolean;
  /** Brief explanation of the metric */
  description: string;
  /** Data source name */
  source: string;
}

// Sequential green (income/spending)
const GREEN_SCALE: [number, number, number][] = [
  [237, 248, 233],
  [116, 196, 118],
  [35, 139, 69],
];

// Sequential blue (transit/walkability)
const BLUE_SCALE: [number, number, number][] = [
  [222, 235, 247],
  [107, 174, 214],
  [33, 113, 181],
];

// Sequential red (safety — higher = worse)
const RED_SCALE: [number, number, number][] = [
  [254, 229, 217],
  [252, 146, 114],
  [203, 24, 29],
];

// Sequential purple (density)
const PURPLE_SCALE: [number, number, number][] = [
  [239, 237, 245],
  [158, 154, 200],
  [106, 81, 163],
];

// Sequential orange (congestion — higher = worse)
const ORANGE_SCALE: [number, number, number][] = [
  [254, 237, 222],
  [253, 174, 107],
  [230, 85, 13],
];

export const METRICS: MetricConfig[] = [
  // Demographics
  {
    key: "population",
    label: "Population",
    category: "Demographics",
    format: "number",
    colorScale: PURPLE_SCALE,
    description: "Total number of residents",
    source: "Census ACS 5-Year",
  },
  {
    key: "per_capita_income",
    label: "Per Capita Income",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Average income per person (all residents, including non-earners)",
    source: "Census ACS 5-Year",
  },
  {
    key: "median_household_income",
    label: "Median Household Income",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Income at the 50th percentile of all households",
    source: "Census ACS 5-Year",
  },
  {
    key: "median_rent",
    label: "Median Rent",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Monthly rent at the 50th percentile",
    source: "Census ACS 5-Year",
  },
  {
    key: "median_home_value",
    label: "Median Home Value",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Owner-occupied home value at the 50th percentile",
    source: "Census ACS 5-Year",
  },
  {
    key: "pop_density_sqmi",
    label: "Pop. Density (per sq mi)",
    category: "Demographics",
    format: "decimal",
    colorScale: PURPLE_SCALE,
    description: "Residents per square mile of land area",
    source: "Census ACS + Gazetteer",
  },

  // Transportation
  {
    key: "pct_drove_alone",
    label: "Drove Alone",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers commuting by car alone",
    source: "Census ACS 5-Year",
  },
  {
    key: "pct_transit",
    label: "Public Transit",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers using public transit",
    source: "Census ACS 5-Year",
  },
  {
    key: "pct_walked",
    label: "Walked",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers walking to work",
    source: "Census ACS 5-Year",
  },
  {
    key: "pct_biked",
    label: "Biked",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers biking to work",
    source: "Census ACS 5-Year",
  },
  {
    key: "pct_wfh",
    label: "Work From Home",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers working from home",
    source: "Census ACS 5-Year",
  },
  {
    key: "avg_walkability",
    label: "Avg. Walkability",
    category: "Transportation",
    format: "decimal",
    colorScale: BLUE_SCALE,
    description: "EPA National Walkability Index (1-20 scale based on intersection density, transit proximity, land use mix)",
    source: "EPA Smart Location Database",
  },
  {
    key: "avg_transit_frequency",
    label: "Transit Service Density",
    category: "Transportation",
    format: "decimal",
    colorScale: BLUE_SCALE,
    description: "Aggregate transit trips per day within 0.25 miles per sq mi of land area. Higher = more transit service available.",
    source: "EPA Smart Location Database",
  },
  {
    key: "pct_zero_car_hh",
    label: "Zero-Car Households",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Percentage of households with no vehicle available",
    source: "EPA Smart Location Database",
  },

  // Safety
  {
    key: "total_fatalities",
    label: "Total Fatalities",
    category: "Safety",
    format: "number",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Total deaths from motor vehicle crashes",
    source: "NHTSA FARS",
  },
  {
    key: "total_crashes",
    label: "Total Crashes",
    category: "Safety",
    format: "number",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Total fatal motor vehicle crashes",
    source: "NHTSA FARS",
  },
  {
    key: "pedestrian_involved_crashes",
    label: "Pedestrian-Involved Crashes",
    category: "Safety",
    format: "number",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Pedestrians involved in fatal crashes",
    source: "NHTSA FARS",
  },
  {
    key: "drunk_driver_crashes",
    label: "Drunk Driver Crashes",
    category: "Safety",
    format: "number",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Drunk drivers involved in fatal crashes",
    source: "NHTSA FARS",
  },

  // Spending
  {
    key: "federal_obligation",
    label: "Federal Obligation ($)",
    category: "Spending",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Total federal infrastructure grants obligated",
    source: "USAspending.gov",
  },
  {
    key: "federal_per_capita",
    label: "Federal $ Per Capita",
    category: "Spending",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Federal infrastructure spending per resident",
    source: "USAspending.gov",
  },

  // Congestion (UMR data — metro-level)
  {
    key: "travel_time_index",
    label: "Travel Time Index",
    category: "Congestion",
    format: "decimal",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Ratio of peak-period travel time to free-flow travel time (1.0 = no congestion)",
    source: "Texas A&M Urban Mobility Report",
  },
  {
    key: "planning_time_index",
    label: "Planning Time Index",
    category: "Congestion",
    format: "decimal",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "How much extra time to budget for reliable arrival (2.0 = budget 2x free-flow)",
    source: "Texas A&M Urban Mobility Report",
  },
  {
    key: "annual_delay_hours",
    label: "Annual Delay (hrs/commuter)",
    category: "Congestion",
    format: "number",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Hours per auto commuter lost to congestion annually",
    source: "Texas A&M Urban Mobility Report",
  },
  {
    key: "congestion_cost",
    label: "Congestion Cost ($/commuter)",
    category: "Congestion",
    format: "currency",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Annual cost of congestion per auto commuter",
    source: "Texas A&M Urban Mobility Report",
  },
];

export const CATEGORIES: MetricCategory[] = [
  "Demographics",
  "Transportation",
  "Safety",
  "Spending",
  "Congestion",
];

export type Granularity = "metro" | "county" | "block_group";

const DATA_FILES: Record<Granularity, string> = {
  metro: "/data/metro_summary.json",
  county: "/data/county_summary.json",
  block_group: "/data/block_group_summary.json",
};

const GEOJSON_FILES: Record<Granularity, string> = {
  metro: "/data/dfw_counties.geojson",
  county: "/data/dfw_counties.geojson",
  block_group: "/data/dfw_block_groups.geojson",
};

/** Load data for any granularity level. */
export async function loadData(granularity: Granularity): Promise<CountyData[]> {
  const file = DATA_FILES[granularity];
  const resp = await fetch(file);
  if (!resp.ok) throw new Error(`Failed to load ${granularity} data: ${resp.status}`);
  return resp.json() as Promise<CountyData[]>;
}

/** Load GeoJSON for any granularity level. */
export async function loadGeoJSON(granularity: Granularity): Promise<GeoJSON.FeatureCollection> {
  const file = GEOJSON_FILES[granularity];
  const resp = await fetch(file);
  if (!resp.ok) throw new Error(`Failed to load ${granularity} GeoJSON: ${resp.status}`);
  return resp.json() as Promise<GeoJSON.FeatureCollection>;
}

/** Format a metric value for display. */
export function formatValue(value: number | null | undefined, format: MetricFormat): string {
  if (value === null || value === undefined || isNaN(value)) return "N/A";
  switch (format) {
    case "currency":
      if (value >= 1_000_000)
        return `$${(value / 1_000_000).toFixed(1)}M`;
      if (value >= 1_000)
        return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
      return `$${value.toFixed(2)}`;
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "decimal":
      return value.toFixed(1);
    case "number":
      return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }
}

/**
 * Interpolate between color stops based on a 0-1 normalized value.
 * Returns [r, g, b, alpha].
 */
export function interpolateColor(
  t: number,
  stops: [number, number, number][],
): [number, number, number, number] {
  if (stops.length < 2) return [...stops[0], 180] as [number, number, number, number];
  const clamped = Math.max(0, Math.min(1, t));
  const segments = stops.length - 1;
  const segment = Math.min(Math.floor(clamped * segments), segments - 1);
  const localT = clamped * segments - segment;

  const a = stops[segment];
  const b = stops[segment + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * localT),
    Math.round(a[1] + (b[1] - a[1]) * localT),
    Math.round(a[2] + (b[2] - a[2]) * localT),
    200, // alpha
  ];
}

/**
 * Compute rank of a county for a given metric among all counties.
 * Returns 1-based rank (1 = highest value). Counties with null values are excluded.
 */
export function computeRank(
  county: CountyData,
  metric: MetricKey,
  allCounties: CountyData[],
): number {
  const valid = allCounties.filter((c) => {
    const v = c[metric];
    return v !== null && v !== undefined && !Number.isNaN(v as number);
  });
  const sorted = [...valid].sort(
    (a, b) => (b[metric] as number) - (a[metric] as number),
  );
  return sorted.findIndex((c) => c.county_fips === county.county_fips) + 1;
}

/** Get ordinal suffix for a number (1st, 2nd, 3rd, etc). */
export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/** Group METRICS by category, preserving CATEGORIES order. */
export function groupMetricsByCategory(): Record<
  MetricCategory,
  MetricConfig[]
> {
  return CATEGORIES.reduce(
    (acc, cat) => {
      acc[cat] = METRICS.filter((m) => m.category === cat);
      return acc;
    },
    {} as Record<MetricCategory, MetricConfig[]>,
  );
}
