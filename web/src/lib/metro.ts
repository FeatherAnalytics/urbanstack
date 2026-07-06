export interface MetroConfig {
  metro_id: string;
  metro_name: string;
  center: [number, number];
  zoom: number;
}

export const METROS: Record<string, MetroConfig> = {
  dfw: {
    metro_id: "dfw",
    metro_name: "Dallas-Fort Worth-Arlington MSA",
    center: [32.78, -96.85],
    zoom: 8,
  },
  chicago: {
    metro_id: "chicago",
    metro_name: "Chicago-Naperville-Elgin MSA",
    center: [41.88, -87.63],
    zoom: 8,
  },
  nyc: {
    metro_id: "nyc",
    metro_name: "New York-Newark-Jersey City MSA",
    center: [40.71, -74.0],
    zoom: 8,
  },
  houston: {
    metro_id: "houston",
    metro_name: "Houston-Pasadena-The Woodlands MSA",
    center: [29.76, -95.37],
    zoom: 8,
  },
  austin: {
    metro_id: "austin",
    metro_name: "Austin-Round Rock-San Marcos MSA",
    center: [30.27, -97.74],
    zoom: 9,
  },
  san_antonio: {
    metro_id: "san_antonio",
    metro_name: "San Antonio-New Braunfels MSA",
    center: [29.42, -98.49],
    zoom: 9,
  },
  boston: {
    metro_id: "boston",
    metro_name: "Boston-Cambridge-Newton MSA",
    center: [42.36, -71.06],
    zoom: 8,
  },
};

export interface RegionConfig {
  region_id: string;
  region_name: string;
  metro_ids: string[];
  center: [number, number];
  zoom: number;
}

export const REGIONS: Record<string, RegionConfig> = {
  northeast: {
    region_id: "northeast",
    region_name: "Northeast",
    metro_ids: ["nyc", "boston"],
    center: [41.5, -72.5],
    zoom: 6,
  },
  texas: {
    region_id: "texas",
    region_name: "Texas",
    metro_ids: ["dfw", "houston", "austin", "san_antonio"],
    center: [30.5, -97.0],
    zoom: 6,
  },
  midwest: {
    region_id: "midwest",
    region_name: "Midwest",
    metro_ids: ["chicago"],
    center: [41.88, -87.63],
    zoom: 7,
  },
};

export const METRO_TO_REGION: Record<string, string> = {};
for (const [regionId, config] of Object.entries(REGIONS)) {
  for (const metroId of config.metro_ids) {
    METRO_TO_REGION[metroId] = regionId;
  }
}
