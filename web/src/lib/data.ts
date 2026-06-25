import { METROS } from "@/lib/metro";

export interface CountyData {
  county_fips: string;
  county_name: string;
  metro_id?: string;
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
  total_annual_ridership: number | null;
  ridership_per_capita: number | null;
  transit_revenue_miles: number | null;
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
  avg_daily_traffic: number | null;
  total_delay_hours: number | null;
  total_congestion_cost: number | null;
  delay_per_capita: number | null;
  congestion_cost_per_capita: number | null;
  fatalities_per_capita: number | null;
  crashes_per_capita: number | null;
  crash_rate_per_1k_commuters: number | null;
  ped_fatality_rate_per_100k: number | null;
  congestion_cost_pct_income: number | null;
  delay_pct_work_hours: number | null;
  federal_per_crash: number | null;
  vehicle_dependency: number | null;
  drunk_driver_crashes_per_capita: number | null;
  pedestrian_crashes_per_capita: number | null;
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
  description: string;
  source: string;
  dateRange?: string;
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
  {
    key: "population",
    label: "Population",
    category: "Demographics",
    format: "number",
    colorScale: PURPLE_SCALE,
    description: "Total number of residents",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "per_capita_income",
    label: "Per Capita Income",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Average income per person (all residents, including non-earners)",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "median_household_income",
    label: "Median Household Income",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Income at the 50th percentile of all households",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "median_rent",
    label: "Median Rent",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Monthly rent at the 50th percentile",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "median_home_value",
    label: "Median Home Value",
    category: "Demographics",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Owner-occupied home value at the 50th percentile",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "pop_density_sqmi",
    label: "Pop. Density (per sq mi)",
    category: "Demographics",
    format: "decimal",
    colorScale: PURPLE_SCALE,
    description: "Residents per square mile of land area",
    source: "Census ACS + Gazetteer",
    dateRange: "2023",
  },

  {
    key: "pct_drove_alone",
    label: "Drove Alone",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers commuting by car alone",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "pct_transit",
    label: "Public Transit",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers using public transit",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "pct_walked",
    label: "Walked",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers walking to work",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "pct_biked",
    label: "Biked",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers biking to work",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "pct_wfh",
    label: "Work From Home",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Share of workers working from home",
    source: "Census ACS 5-Year",
    dateRange: "2023",
  },
  {
    key: "avg_walkability",
    label: "Avg. Walkability",
    category: "Transportation",
    format: "decimal",
    colorScale: BLUE_SCALE,
    description: "EPA National Walkability Index (1–20 scale based on intersection density, transit proximity, land use mix)",
    source: "EPA Smart Location Database",
    dateRange: "2021",
  },
  {
    key: "avg_transit_frequency",
    label: "Transit Service Density",
    category: "Transportation",
    format: "decimal",
    colorScale: BLUE_SCALE,
    description: "Aggregate transit trips per day within 0.25 miles per sq mi of land area. Higher = more transit service available.",
    source: "EPA Smart Location Database",
    dateRange: "2021",
  },
  {
    key: "pct_zero_car_hh",
    label: "Zero-Car Households",
    category: "Transportation",
    format: "percent",
    colorScale: BLUE_SCALE,
    description: "Percentage of households with no vehicle available",
    source: "EPA Smart Location Database",
    dateRange: "2021",
  },
  {
    key: "total_annual_ridership",
    label: "Est. Annual Transit Ridership",
    category: "Transportation",
    format: "number",
    colorScale: BLUE_SCALE,
    description: "Estimated annual transit trips, distributed proportionally by share of transit commuters in this area",
    source: "NTD + Census ACS",
    dateRange: "2025",
  },
  {
    key: "ridership_per_capita",
    label: "Est. Transit Rides Per Capita",
    category: "Transportation",
    format: "decimal",
    colorScale: BLUE_SCALE,
    description: "Estimated annual transit trips per resident, based on proportional ridership distribution",
    source: "NTD + Census ACS",
    dateRange: "2025",
  },
  {
    key: "transit_revenue_miles",
    label: "Transit Revenue Miles",
    category: "Transportation",
    format: "number",
    colorScale: BLUE_SCALE,
    description: "Total miles traveled by transit vehicles while in passenger service across DFW agencies (DART, Trinity Metro, DCTA)",
    source: "NTD Monthly Ridership",
    dateRange: "2025",
  },
  {
    key: "avg_daily_traffic",
    label: "Avg. Daily Traffic Volume",
    category: "Transportation",
    format: "number",
    colorScale: PURPLE_SCALE,
    description: "Average daily vehicle count across permanent FHWA traffic monitoring stations in this area",
    source: "FHWA TMAS",
    dateRange: "2023",
  },

  {
    key: "total_fatalities",
    label: "Total Fatalities",
    category: "Safety",
    format: "number",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Total deaths from motor vehicle crashes",
    source: "NHTSA FARS",
    dateRange: "2015–2022",
  },
  {
    key: "total_crashes",
    label: "Total Fatal Crashes",
    category: "Safety",
    format: "number",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Total fatal motor vehicle crashes (at least one death)",
    source: "NHTSA FARS",
    dateRange: "2015–2022",
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
    dateRange: "2015–2022",
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
    dateRange: "2015–2022",
  },
  {
    key: "fatalities_per_capita",
    label: "Fatalities Per Capita",
    category: "Safety",
    format: "decimal",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Motor vehicle crash fatalities per resident",
    source: "NHTSA FARS + Census ACS",
    dateRange: "2015–2022",
  },
  {
    key: "crashes_per_capita",
    label: "Fatal Crashes Per Capita",
    category: "Safety",
    format: "decimal",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Fatal motor vehicle crashes per resident",
    source: "NHTSA FARS + Census ACS",
    dateRange: "2015–2022",
  },

  {
    key: "federal_obligation",
    label: "Federal Obligation ($)",
    category: "Spending",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Total federal infrastructure grants obligated",
    source: "USAspending.gov",
    dateRange: "2020–2024",
  },
  {
    key: "federal_per_capita",
    label: "Federal $ Per Capita",
    category: "Spending",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Federal infrastructure spending per resident",
    source: "USAspending.gov",
    dateRange: "2020–2024",
  },

  {
    key: "travel_time_index",
    label: "Travel Time Index",
    category: "Congestion",
    format: "decimal",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Ratio of peak-period travel time to free-flow travel time (1.0 = no congestion). Metro-level measure.",
    source: "Texas A&M Urban Mobility Report",
    dateRange: "2024",
  },
  {
    key: "planning_time_index",
    label: "Planning Time Index",
    category: "Congestion",
    format: "decimal",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "How much extra time to budget for reliable arrival (2.0 = budget 2x free-flow). Metro-level measure.",
    source: "Texas A&M Urban Mobility Report",
    dateRange: "2024",
  },
  {
    key: "annual_delay_hours",
    label: "Annual Delay (hrs/commuter)",
    category: "Congestion",
    format: "number",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Hours per auto commuter (workers who drive to work alone) lost to congestion annually. Metro-level measure.",
    source: "Texas A&M Urban Mobility Report",
    dateRange: "2024",
  },
  {
    key: "congestion_cost",
    label: "Congestion Cost ($/commuter)",
    category: "Congestion",
    format: "currency",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Annual cost of congestion per auto commuter (workers who drive to work alone). Metro-level measure.",
    source: "Texas A&M Urban Mobility Report",
    dateRange: "2024",
  },
  {
    key: "total_delay_hours",
    label: "Est. Total Delay (hours)",
    category: "Congestion",
    format: "number",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Estimated total annual hours of delay from congestion, based on number of auto commuters (workers who drive to work alone) and metro-level delay rate",
    source: "UMR + Census ACS",
    dateRange: "2024",
  },
  {
    key: "total_congestion_cost",
    label: "Est. Congestion Cost ($)",
    category: "Congestion",
    format: "currency",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Estimated total annual cost of congestion, based on number of auto commuters (workers who drive to work alone) and metro-level cost rate",
    source: "UMR + Census ACS",
    dateRange: "2024",
  },
  {
    key: "delay_per_capita",
    label: "Est. Delay Per Capita (hrs)",
    category: "Congestion",
    format: "decimal",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Estimated annual hours of congestion delay per resident",
    source: "UMR + Census ACS",
    dateRange: "2024",
  },
  {
    key: "congestion_cost_per_capita",
    label: "Est. Congestion Cost Per Capita",
    category: "Congestion",
    format: "currency",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Estimated annual cost of congestion per resident",
    source: "UMR + Census ACS",
    dateRange: "2024",
  },
  {
    key: "congestion_cost_pct_income",
    label: "Congestion Cost (% of Income)",
    category: "Congestion",
    format: "percent",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Estimated congestion cost per capita as a percentage of per capita income",
    source: "UMR + Census ACS",
    dateRange: "2024",
  },
  {
    key: "delay_pct_work_hours",
    label: "Delay (% of Work Year)",
    category: "Congestion",
    format: "percent",
    colorScale: ORANGE_SCALE,
    invertSentiment: true,
    description: "Estimated congestion delay per commuter as a percentage of a standard 2,080-hour work year",
    source: "UMR + Census ACS",
    dateRange: "2024",
  },
  {
    key: "crash_rate_per_1k_commuters",
    label: "Crash Rate (per 1K Commuters)",
    category: "Safety",
    format: "decimal",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Motor vehicle crash fatalities per 1,000 commuters, normalizing safety by commuting population",
    source: "NHTSA FARS + Census ACS",
    dateRange: "2015–2022",
  },
  {
    key: "ped_fatality_rate_per_100k",
    label: "Pedestrian Fatality Rate (per 100K)",
    category: "Safety",
    format: "decimal",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Pedestrians involved in fatal crashes per 100,000 residents — standard public health rate",
    source: "NHTSA FARS + Census ACS",
    dateRange: "2015–2022",
  },
  {
    key: "drunk_driver_crashes_per_capita",
    label: "Drunk Driver Rate (per 100K)",
    category: "Safety",
    format: "decimal",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Drunk drivers involved in fatal crashes per 100,000 residents",
    source: "NHTSA FARS + Census ACS",
    dateRange: "2015–2022",
  },
  {
    key: "pedestrian_crashes_per_capita",
    label: "Pedestrian Crash Rate (per 100K)",
    category: "Safety",
    format: "decimal",
    colorScale: RED_SCALE,
    invertSentiment: true,
    description: "Pedestrians involved in fatal crashes per 100,000 residents",
    source: "NHTSA FARS + Census ACS",
    dateRange: "2015–2022",
  },
  {
    key: "federal_per_crash",
    label: "Federal $ per Fatal Crash",
    category: "Spending",
    format: "currency",
    colorScale: GREEN_SCALE,
    description: "Federal infrastructure spending per fatal crash — investment relative to safety outcomes",
    source: "USAspending + NHTSA FARS",
    dateRange: "2020–2024",
  },
  {
    key: "vehicle_dependency",
    label: "Vehicle Dependency",
    category: "Transportation",
    format: "decimal",
    colorScale: PURPLE_SCALE,
    invertSentiment: true,
    description: "Composite auto-dependency score: (1 − zero-car households) × drove-alone share. Higher = more car-dependent.",
    source: "Census ACS + EPA SLD",
    dateRange: "2023",
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

export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
// yagni: inline const, create config.ts when there are 3+ config values
export const R2_BASE_URL = process.env.NEXT_PUBLIC_R2_URL
  ?? "https://pub-67ffcc9780314ab6a2cb7c45ad6398eb.r2.dev/exports";

function dataPath(metroId: string, granularity: Granularity): string {
  return `${BASE_PATH}/data/${metroId}/${granularity}_summary.json`;
}

function geoJsonPath(metroId: string, granularity: Granularity): string {
  const file = granularity === "block_group" ? "block_groups" : "counties";
  return `${BASE_PATH}/data/${metroId}/${file}.geojson`;
}

/** Load data for any granularity level. */
export async function loadData(metroId: string, granularity: Granularity): Promise<CountyData[]> {
  const file = dataPath(metroId, granularity);
  const resp = await fetch(file);
  if (!resp.ok) throw new Error(`Failed to load ${granularity} data: ${resp.status}`);
  return resp.json() as Promise<CountyData[]>;
}

/** Load GeoJSON for any granularity level. */
export async function loadGeoJSON(metroId: string, granularity: Granularity): Promise<GeoJSON.FeatureCollection> {
  const file = geoJsonPath(metroId, granularity);
  const resp = await fetch(file);
  if (!resp.ok) throw new Error(`Failed to load ${granularity} GeoJSON: ${resp.status}`);
  return resp.json() as Promise<GeoJSON.FeatureCollection>;
}

export interface OverlayIndex {
  years: number[];
}

export async function loadOverlayIndex(metroId: string): Promise<OverlayIndex | null> {
  try {
    const resp = await fetch(`${BASE_PATH}/data/${metroId}/overlays/index.json`);
    if (!resp.ok) return null;
    return resp.json() as Promise<OverlayIndex>;
  } catch {
    return null;
  }
}

export async function loadYearOverlay(
  metroId: string,
  year: number,
): Promise<Record<string, Partial<CountyData>> | null> {
  try {
    const resp = await fetch(`${BASE_PATH}/data/${metroId}/overlays/county_${year}.json`);
    if (!resp.ok) return null;
    const records = (await resp.json()) as Partial<CountyData>[];
    const map: Record<string, Partial<CountyData>> = {};
    for (const r of records) {
      if (r.county_fips) map[r.county_fips] = r;
    }
    return map;
  } catch {
    return null;
  }
}

export function mergeOverlay(
  base: CountyData[],
  overlay: Record<string, Partial<CountyData>>,
): CountyData[] {
  return base.map((c) => {
    const over = overlay[c.county_fips];
    return over ? { ...c, ...over } : c;
  });
}

export async function loadAllData(granularity: Granularity): Promise<CountyData[]> {
  const metroIds = Object.keys(METROS);
  const results = await Promise.allSettled(
    metroIds.map((id) => loadData(id, granularity))
  );
  const data = results
    .filter((r): r is PromiseFulfilledResult<CountyData[]> => r.status === "fulfilled")
    .flatMap((r) => r.value);
  if (data.length === 0) throw new Error(`No ${granularity} data loaded for any metro`);
  return data;
}

export async function loadAllGeoJSON(granularity: Granularity): Promise<GeoJSON.FeatureCollection> {
  const metroIds = Object.keys(METROS);
  const results = await Promise.allSettled(
    metroIds.map((id) => loadGeoJSON(id, granularity))
  );
  const features = results
    .filter((r): r is PromiseFulfilledResult<GeoJSON.FeatureCollection> => r.status === "fulfilled")
    .flatMap((r) => r.value.features);
  if (features.length === 0) throw new Error(`No ${granularity} GeoJSON loaded for any metro`);
  return { type: "FeatureCollection", features };
}

export async function loadAllOverlayIndexes(): Promise<Record<string, OverlayIndex>> {
  const metroIds = Object.keys(METROS);
  const results = await Promise.allSettled(
    metroIds.map(async (id) => ({ id, index: await loadOverlayIndex(id) }))
  );
  const indexes: Record<string, OverlayIndex> = {};
  for (const r of results) {
    if (r.status === "fulfilled" && r.value.index) {
      indexes[r.value.id] = r.value.index;
    }
  }
  return indexes;
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
  if (!Number.isFinite(t)) return [...stops[0], 180] as [number, number, number, number];
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

// ============================================================================
// Viewport-Based Color Scaling
// ============================================================================

export type ColorScaleMode = "global" | "viewport";

export interface ViewportBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export function computeMinMax(
  counties: CountyData[],
  metricKey: MetricKey,
  visibleIds: Set<string> | null,
): { min: number; max: number } {
  const filtered = visibleIds
    ? counties.filter((c) => visibleIds.has(c.county_fips))
    : counties;
  const values = filtered
    .map((c) => c[metricKey] as number | null)
    .filter((v): v is number => v !== null && v !== undefined && !Number.isNaN(v));
  if (values.length === 0) return { min: 0, max: 0 };
  let min = Infinity;
  let max = -Infinity;
  for (const v of values) {
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return { min, max };
}

function centroid(coords: number[][]): [number, number] {
  let lon = 0;
  let lat = 0;
  const n = coords.length;
  for (const [x, y] of coords) {
    lon += x;
    lat += y;
  }
  return [lon / n, lat / n];
}

export function getVisibleGeoIds(
  geojson: GeoJSON.FeatureCollection,
  bounds: ViewportBounds,
): Set<string> {
  const ids = new Set<string>();
  for (const feature of geojson.features) {
    const geoId = feature.properties?.GEOID as string | undefined;
    if (!geoId) continue;
    const geom = feature.geometry;
    let ring: number[][] | undefined;
    if (geom.type === "Polygon") {
      ring = geom.coordinates[0] as number[][];
    } else if (geom.type === "MultiPolygon") {
      ring = geom.coordinates[0][0] as number[][];
    }
    if (!ring || ring.length === 0) continue;
    const [lon, lat] = centroid(ring);
    if (lon >= bounds.west && lon <= bounds.east && lat >= bounds.south && lat <= bounds.north) {
      ids.add(geoId);
    }
  }
  return ids;
}

// ============================================================================
// Bivariate Choropleth Utilities
// ============================================================================

/** Stevens purple-teal bivariate palette (colorblind-safe). Rows = primary bins, cols = secondary bins. */
export const BIVARIATE_PALETTE: [number, number, number][][] = [
  [[232, 232, 232], [172, 228, 228], [90, 200, 200]],
  [[223, 176, 214], [165, 173, 211], [86, 152, 185]],
  [[190, 100, 172], [140, 98, 170], [59, 73, 148]],
];

export function computeQuantileBins(values: number[], bins: number): number[] {
  if (values.length === 0) return Array(bins - 1).fill(0);
  const sorted = [...values].sort((a, b) => a - b);
  const breaks: number[] = [];
  for (let i = 1; i < bins; i++) {
    const idx = Math.floor((i / bins) * sorted.length);
    breaks.push(sorted[Math.min(idx, sorted.length - 1)]);
  }
  return breaks;
}

export function classifyBin(value: number, breaks: number[]): number {
  for (let i = 0; i < breaks.length; i++) {
    if (value <= breaks[i]) return i;
  }
  return breaks.length;
}

export function getBivariateColor(
  primaryBin: number,
  secondaryBin: number,
  alpha: number,
): [number, number, number, number] {
  const row = Math.max(0, Math.min(2, primaryBin));
  const col = Math.max(0, Math.min(2, secondaryBin));
  const rgb = BIVARIATE_PALETTE[row][col];
  return [rgb[0], rgb[1], rgb[2], alpha];
}

export interface MetricCombo {
  key: string;
  label: string;
  primary: MetricKey;
  secondary: MetricKey;
  description: string;
}

export const METRIC_COMBOS: MetricCombo[] = [
  {
    key: "walkability-safety",
    label: "Walkability × Safety",
    primary: "avg_walkability",
    secondary: "ped_fatality_rate_per_100k",
    description: "Wali & Frank (2024): walkable areas reduce total fatalities but increase pedestrian/cyclist fatality rates by 4.9% per walkability unit.",
  },
  {
    key: "transit-income",
    label: "Transit × Income",
    primary: "avg_transit_frequency",
    secondary: "per_capita_income",
    description: "Do low-income areas have transit access? Based on Griffin & Sener (2016) DFW equity analysis.",
  },
  {
    key: "density-ridership",
    label: "Density × Ridership",
    primary: "pop_density_sqmi",
    secondary: "ridership_per_capita",
    description: "Are dense areas actually using transit? Reveals mismatch between density and ridership.",
  },
  {
    key: "car-dep-congestion",
    label: "Car Dep. × Congestion",
    primary: "vehicle_dependency",
    secondary: "congestion_cost_per_capita",
    description: "High vehicle dependency + high congestion cost = paying the most for lack of alternatives.",
  },
  {
    key: "zero-car-walkability",
    label: "Zero-Car × Walkability",
    primary: "pct_zero_car_hh",
    secondary: "avg_walkability",
    description: "Zero-car households in non-walkable areas face the worst mobility constraints.",
  },
  {
    key: "income-commute",
    label: "Income × Transit Use",
    primary: "per_capita_income",
    secondary: "pct_transit",
    description: "Do higher-income areas avoid transit? Reveals class stratification in transportation choices.",
  },
  {
    key: "income-vehicle-dep",
    label: "Income × Car Dep.",
    primary: "per_capita_income",
    secondary: "vehicle_dependency",
    description: "Low income + high car dependency = forced car ownership. Financial vulnerability indicator.",
  },
];
