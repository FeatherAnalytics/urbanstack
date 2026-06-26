import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ClassifiedLegend } from "@/components/ClassifiedLegend";
import { METRICS, NO_DATA_COLOR, generateClassifiedPalette } from "@/lib/data";

const palette = generateClassifiedPalette(METRICS[0].colorScale, 5);
const breaks = [100, 200, 300, 400];

describe("ClassifiedLegend", () => {
  it("renders 6 swatches", () => {
    render(
      <ClassifiedLegend
        metric={METRICS[0]}
        palette={palette}
        breaks={breaks}
        selectedBins={new Set()}
        onSelectionChange={() => {}}
      />,
    );
    const swatches = screen.getAllByRole("button", { name: /bin/i });
    expect(swatches.length).toBe(6);
  });

  it("toggles bin on click", () => {
    const onChange = vi.fn();
    render(
      <ClassifiedLegend
        metric={METRICS[0]}
        palette={palette}
        breaks={breaks}
        selectedBins={new Set()}
        onSelectionChange={onChange}
      />,
    );
    const swatches = screen.getAllByRole("button", { name: /bin/i });
    fireEvent.click(swatches[1]); // click bin 1
    expect(onChange).toHaveBeenCalledWith(new Set([1]));
  });

  it("shows clear button when bins selected", () => {
    render(
      <ClassifiedLegend
        metric={METRICS[0]}
        palette={palette}
        breaks={breaks}
        selectedBins={new Set([2])}
        onSelectionChange={() => {}}
      />,
    );
    expect(screen.getByText("Clear")).toBeInTheDocument();
  });

  it("hides clear button when no bins selected", () => {
    render(
      <ClassifiedLegend
        metric={METRICS[0]}
        palette={palette}
        breaks={breaks}
        selectedBins={new Set()}
        onSelectionChange={() => {}}
      />,
    );
    expect(screen.queryByText("Clear")).not.toBeInTheDocument();
  });
});
