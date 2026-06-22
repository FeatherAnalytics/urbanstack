import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ColorLegend } from "../ColorLegend";
import { METRICS } from "@/lib/data";

const walkability = METRICS.find((m) => m.key === "avg_walkability")!;
const safety = METRICS.find((m) => m.key === "ped_fatality_rate_per_100k")!;

describe("ColorLegend", () => {
  it("renders gradient bar in single-metric mode", () => {
    render(
      <ColorLegend
        primaryMetric={walkability}
        secondaryMetric={null}
        primaryMinMax={{ min: 2.1, max: 14.8 }}
        secondaryMinMax={null}
        colorScaleMode="global"
        onToggleMode={() => {}}
        granularity="county"
      />,
    );
    expect(screen.getByText("Avg. Walkability")).toBeInTheDocument();
    expect(screen.getByText("2.1")).toBeInTheDocument();
    expect(screen.getByText("14.8")).toBeInTheDocument();
  });

  it("renders 3x3 grid in bivariate mode", () => {
    render(
      <ColorLegend
        primaryMetric={walkability}
        secondaryMetric={safety}
        primaryMinMax={{ min: 2, max: 15 }}
        secondaryMinMax={{ min: 0, max: 50 }}
        colorScaleMode="global"
        onToggleMode={() => {}}
        granularity="county"
      />,
    );
    expect(screen.getByTestId("bivariate-grid")).toBeInTheDocument();
  });

  it("hides scale toggle at metro granularity", () => {
    render(
      <ColorLegend
        primaryMetric={walkability}
        secondaryMetric={null}
        primaryMinMax={{ min: 2, max: 15 }}
        secondaryMinMax={null}
        colorScaleMode="global"
        onToggleMode={() => {}}
        granularity="metro"
      />,
    );
    expect(screen.queryByText(/Scale/)).not.toBeInTheDocument();
  });
});
