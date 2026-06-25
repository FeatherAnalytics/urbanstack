import { describe, it, expect } from "vitest";
import { interpolateColor, formatValue, computeDisplayRange, getVisibleGeoIds, computeQuantileBins, getBivariateColor, BIVARIATE_PALETTE, METRIC_COMBOS, computeRank, ordinal, formatRank } from "@/lib/data";
import type { CountyData } from "@/lib/data";

describe("interpolateColor", () => {
  it("returns low stop at t=0", () => {
    const stops: [number, number, number][] = [[0, 0, 0], [128, 128, 128], [255, 255, 255]];
    const [r, g, b] = interpolateColor(0, stops);
    expect(r).toBe(0);
    expect(g).toBe(0);
    expect(b).toBe(0);
  });

  it("returns high stop at t=1", () => {
    const stops: [number, number, number][] = [[0, 0, 0], [128, 128, 128], [255, 255, 255]];
    const [r, g, b] = interpolateColor(1, stops);
    expect(r).toBe(255);
    expect(g).toBe(255);
    expect(b).toBe(255);
  });
});

describe("formatValue", () => {
  it("formats currency", () => {
    expect(formatValue(1500000, "currency")).toBe("$1.5M");
  });

  it("returns N/A for null", () => {
    expect(formatValue(null, "number")).toBe("N/A");
  });

  it("shows significant digits for very small decimals", () => {
    expect(formatValue(0.0009, "decimal")).toBe("0.0009");
    expect(formatValue(0.045, "decimal")).toBe("0.045");
    expect(formatValue(0.005, "decimal")).toBe("0.005");
  });

  it("keeps toFixed(1) for normal decimals", () => {
    expect(formatValue(11.9, "decimal")).toBe("11.9");
    expect(formatValue(2.3, "decimal")).toBe("2.3");
    expect(formatValue(0.7, "decimal")).toBe("0.7");
    expect(formatValue(0.1, "decimal")).toBe("0.1");
  });
});

describe("computeDisplayRange", () => {
  const counties: CountyData[] = [
    { county_fips: "001", county_name: "A", per_capita_income: 30000 } as CountyData,
    { county_fips: "002", county_name: "B", per_capita_income: 50000 } as CountyData,
    { county_fips: "003", county_name: "C", per_capita_income: 40000 } as CountyData,
  ];

  it("computes global min/max when visibleIds is null", () => {
    const result = computeDisplayRange(counties, "per_capita_income", null);
    expect(result).toEqual({ min: 30000, max: 50000 });
  });

  it("computes viewport min/max when visibleIds is provided", () => {
    const result = computeDisplayRange(counties, "per_capita_income", new Set(["001", "003"]));
    expect(result).toEqual({ min: 30000, max: 40000 });
  });

  it("returns { min: 0, max: 0 } when no valid values", () => {
    const empty: CountyData[] = [
      { county_fips: "001", county_name: "A", per_capita_income: null } as CountyData,
    ];
    const result = computeDisplayRange(empty, "per_capita_income", null);
    expect(result).toEqual({ min: 0, max: 0 });
  });
});

describe("getVisibleGeoIds", () => {
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { GEOID: "001" },
        geometry: { type: "Polygon", coordinates: [[[-97, 33], [-96, 33], [-96, 34], [-97, 34], [-97, 33]]] },
      },
      {
        type: "Feature",
        properties: { GEOID: "002" },
        geometry: { type: "Polygon", coordinates: [[[-90, 40], [-89, 40], [-89, 41], [-90, 41], [-90, 40]]] },
      },
    ],
  };

  it("returns GEOIDs whose centroid falls within bounds", () => {
    const bounds = { west: -98, south: 32, east: -95, north: 35 };
    const result = getVisibleGeoIds(geojson, bounds);
    expect(result).toEqual(new Set(["001"]));
  });

  it("returns all GEOIDs when bounds contain all features", () => {
    const bounds = { west: -100, south: 30, east: -80, north: 45 };
    const result = getVisibleGeoIds(geojson, bounds);
    expect(result).toEqual(new Set(["001", "002"]));
  });
});

describe("computeQuantileBins", () => {
  it("splits 9 values into 3 bins with 2 breakpoints", () => {
    const values = [1, 2, 3, 4, 5, 6, 7, 8, 9];
    const breaks = computeQuantileBins(values, 3);
    expect(breaks).toHaveLength(2);
    expect(breaks[0]).toBe(4);
    expect(breaks[1]).toBe(7);
  });

  it("handles single value (all same bin)", () => {
    const values = [5, 5, 5];
    const breaks = computeQuantileBins(values, 3);
    expect(breaks).toHaveLength(2);
    expect(breaks[0]).toBe(5);
    expect(breaks[1]).toBe(5);
  });

  it("handles empty array", () => {
    const breaks = computeQuantileBins([], 3);
    expect(breaks).toEqual([0, 0]);
  });
});

describe("getBivariateColor", () => {
  it("returns gray for bin (0,0) — low-low", () => {
    const [r, g, b, a] = getBivariateColor(0, 0, 200);
    expect([r, g, b]).toEqual(BIVARIATE_PALETTE[0][0]);
    expect(a).toBe(200);
  });

  it("returns deep blue-purple for bin (2,2) — high-high", () => {
    const [r, g, b, a] = getBivariateColor(2, 2, 120);
    expect([r, g, b]).toEqual(BIVARIATE_PALETTE[2][2]);
    expect(a).toBe(120);
  });

  it("clamps out-of-range bins", () => {
    const color = getBivariateColor(5, -1, 200);
    expect(color).toBeDefined();
  });
});

describe("METRIC_COMBOS", () => {
  it("has 10 pre-built combos", () => {
    expect(METRIC_COMBOS).toHaveLength(10);
  });

  it("each combo has distinct primary and secondary keys", () => {
    for (const combo of METRIC_COMBOS) {
      expect(combo.key).toBeTruthy();
      expect(combo.primary).not.toBe(combo.secondary);
    }
  });
});

describe("formatRank", () => {
  const counties = [
    { county_fips: "001", county_name: "A", population: 5000 },
    { county_fips: "002", county_name: "B", population: 3000 },
    { county_fips: "003", county_name: "C", population: 1000 },
    { county_fips: "004", county_name: "D", population: null },
  ] as CountyData[];

  it("formats rank with total count", () => {
    expect(formatRank(counties[0], "population", counties)).toBe("1st of 3");
  });

  it("excludes null values from count", () => {
    expect(formatRank(counties[2], "population", counties)).toBe("3rd of 3");
  });
});
