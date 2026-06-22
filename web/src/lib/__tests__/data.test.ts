import { describe, it, expect } from "vitest";
import { interpolateColor, formatValue, computeMinMax, getVisibleGeoIds } from "@/lib/data";
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
});

describe("computeMinMax", () => {
  const counties: CountyData[] = [
    { county_fips: "001", county_name: "A", per_capita_income: 30000 } as CountyData,
    { county_fips: "002", county_name: "B", per_capita_income: 50000 } as CountyData,
    { county_fips: "003", county_name: "C", per_capita_income: 40000 } as CountyData,
  ];

  it("computes global min/max when visibleIds is null", () => {
    const result = computeMinMax(counties, "per_capita_income", null);
    expect(result).toEqual({ min: 30000, max: 50000 });
  });

  it("computes viewport min/max when visibleIds is provided", () => {
    const result = computeMinMax(counties, "per_capita_income", new Set(["001", "003"]));
    expect(result).toEqual({ min: 30000, max: 40000 });
  });

  it("returns { min: 0, max: 0 } when no valid values", () => {
    const empty: CountyData[] = [
      { county_fips: "001", county_name: "A", per_capita_income: null } as CountyData,
    ];
    const result = computeMinMax(empty, "per_capita_income", null);
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
