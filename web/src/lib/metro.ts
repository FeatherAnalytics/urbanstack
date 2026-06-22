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
};
