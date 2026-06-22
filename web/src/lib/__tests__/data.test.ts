import { describe, it, expect } from "vitest";
import { interpolateColor, formatValue } from "@/lib/data";

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
