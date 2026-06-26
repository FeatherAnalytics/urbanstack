# Classified Color Scale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the continuous gradient choropleth with a classified (5 quantile bins + 1 no-data) color scale, with interactive bucket selection in the legend, map highlighting, and a redesigned bottom panel.

**Architecture:** New classification functions in `data.ts` (`computeQuantileBreaks`, `classifyValue`, `generateClassifiedPalette`, `stabilizeViewportBounds`). New `ClassifiedLegend` component replaces `GradientLegend`. ChoroplethMap's `getFillColor` switches from `interpolateColor` to classify-and-lookup. ComparisonChart layout flipped and bars colored by bucket. All state orchestrated in `page.tsx`.

**Tech Stack:** Next.js 16, React 19, TypeScript, deck.gl 9, Tailwind 4, Vitest

**Spec:** `docs/superpowers/specs/2026-06-25-classified-color-scale-design.md`

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `web/src/lib/data.ts` | Classification engine: 4 new functions + 2 constants | Modify |
| `web/src/lib/__tests__/data.test.ts` | Unit tests for all new functions | Modify |
| `web/src/components/ClassifiedLegend.tsx` | Clickable 6-swatch legend with multi-select | Create |
| `web/src/components/__tests__/ClassifiedLegend.test.tsx` | Legend render + interaction tests | Create |
| `web/src/components/ColorLegend.tsx` | Route to ClassifiedLegend or BivariateLegend | Modify |
| `web/src/components/ChoroplethMap.tsx` | getFillColor/getLineColor for classified + highlight | Modify |
| `web/src/components/ComparisonChart.tsx` | Flipped layout, bucket-colored bars, bucket filter | Modify |
| `web/src/app/page.tsx` | State, memos, viewport stabilization, prop wiring | Modify |

---

### Task 1: Classification Engine — Unit Tests + Implementation

**Files:**
- Modify: `web/src/lib/data.ts` (add after the bivariate utilities section, ~line 943)
- Modify: `web/src/lib/__tests__/data.test.ts`

- [ ] **Step 1: Write failing tests for computeQuantileBreaks**

Add to `web/src/lib/__tests__/data.test.ts`:

```typescript
import {
  // ... existing imports ...
  computeQuantileBreaks,
  classifyValue,
  generateClassifiedPalette,
  stabilizeViewportBounds,
  QUANTILE_BIN_COUNT,
  NO_DATA_COLOR,
} from "@/lib/data";

describe("computeQuantileBreaks", () => {
  it("divides 10 values into 5 bins with 4 breakpoints", () => {
    const values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    const breaks = computeQuantileBreaks(values, 5);
    expect(breaks).toHaveLength(4);
    expect(breaks[0]).toBe(20); // 20th percentile
    expect(breaks[1]).toBe(40); // 40th percentile
    expect(breaks[2]).toBe(60); // 60th percentile
    expect(breaks[3]).toBe(80); // 80th percentile
  });

  it("returns zeros for empty array", () => {
    expect(computeQuantileBreaks([], 5)).toEqual([0, 0, 0, 0]);
  });

  it("handles all identical values", () => {
    const breaks = computeQuantileBreaks([42, 42, 42, 42, 42], 5);
    expect(breaks).toEqual([42, 42, 42, 42]);
  });

  it("handles unsorted input", () => {
    const sorted = computeQuantileBreaks([10, 20, 30, 40, 50], 5);
    const unsorted = computeQuantileBreaks([50, 10, 40, 20, 30], 5);
    expect(unsorted).toEqual(sorted);
  });

  it("handles fewer values than bins", () => {
    const breaks = computeQuantileBreaks([10, 20], 5);
    expect(breaks).toHaveLength(4);
  });
});
```

- [ ] **Step 2: Write failing tests for classifyValue**

Add to the same test file:

```typescript
describe("classifyValue", () => {
  const breaks = [20, 40, 60, 80]; // 5 bins

  it("classifies values into correct bins", () => {
    expect(classifyValue(10, breaks)).toBe(1);  // ≤ 20
    expect(classifyValue(30, breaks)).toBe(2);  // 21-40
    expect(classifyValue(50, breaks)).toBe(3);  // 41-60
    expect(classifyValue(70, breaks)).toBe(4);  // 61-80
    expect(classifyValue(90, breaks)).toBe(5);  // > 80
  });

  it("assigns boundary values to lower bin", () => {
    expect(classifyValue(20, breaks)).toBe(1);  // exactly on break → lower
    expect(classifyValue(40, breaks)).toBe(2);
    expect(classifyValue(80, breaks)).toBe(4);
  });

  it("returns -1 for null", () => {
    expect(classifyValue(null, breaks)).toBe(-1);
  });

  it("returns -1 for zero", () => {
    expect(classifyValue(0, breaks)).toBe(-1);
  });

  it("returns -1 for NaN", () => {
    expect(classifyValue(NaN, breaks)).toBe(-1);
  });

  it("handles all-identical breaks", () => {
    expect(classifyValue(42, [42, 42, 42, 42])).toBe(1);
    expect(classifyValue(43, [42, 42, 42, 42])).toBe(5);
  });
});
```

- [ ] **Step 3: Write failing tests for generateClassifiedPalette and stabilizeViewportBounds**

```typescript
describe("generateClassifiedPalette", () => {
  const colorScale: [number, number, number][] = [
    [200, 200, 200],
    [100, 100, 100],
    [0, 0, 0],
  ];

  it("returns array with binCount + 1 entries", () => {
    const palette = generateClassifiedPalette(colorScale, 5);
    expect(palette).toHaveLength(6);
  });

  it("first entry is NO_DATA_COLOR", () => {
    const palette = generateClassifiedPalette(colorScale, 5);
    expect(palette[0]).toEqual(NO_DATA_COLOR);
  });

  it("last entry matches the high stop of the color ramp", () => {
    const palette = generateClassifiedPalette(colorScale, 5);
    // Index 5 = binIndex 4 (highest bin) sampled at t=1.0
    expect(palette[5][0]).toBe(0);
    expect(palette[5][1]).toBe(0);
    expect(palette[5][2]).toBe(0);
  });

  it("first quantile entry matches the low stop", () => {
    const palette = generateClassifiedPalette(colorScale, 5);
    // Index 1 = binIndex 0 (lowest bin) sampled at t=0.0
    expect(palette[1][0]).toBe(200);
    expect(palette[1][1]).toBe(200);
    expect(palette[1][2]).toBe(200);
  });
});

describe("stabilizeViewportBounds", () => {
  it("rounds bounds to 0.1 degree precision", () => {
    const result = stabilizeViewportBounds({
      west: -96.853, east: -96.747, south: 32.714, north: 32.846,
    });
    expect(result.west).toBe(-96.9);
    expect(result.east).toBe(-96.7);
    expect(result.south).toBe(32.7);
    expect(result.north).toBe(32.8);
  });

  it("small perturbation produces same output", () => {
    const a = stabilizeViewportBounds({ west: -96.83, east: -96.77, south: 32.72, north: 32.78 });
    const b = stabilizeViewportBounds({ west: -96.84, east: -96.76, south: 32.73, north: 32.79 });
    expect(a).toEqual(b);
  });
});
```

- [ ] **Step 4: Run tests to verify all fail**

Run: `cd web && npx vitest run src/lib/__tests__/data.test.ts`
Expected: FAIL — functions not exported from data.ts

- [ ] **Step 5: Implement all 4 functions and 2 constants**

Add to `web/src/lib/data.ts` after the bivariate section (after line 943):

```typescript
// ============================================================================
// Classified (Quantile) Color Scale
// ============================================================================

export const QUANTILE_BIN_COUNT = 5;
export const NO_DATA_COLOR: [number, number, number, number] = [200, 200, 200, 80];

export function computeQuantileBreaks(values: number[], binCount: number): number[] {
  if (values.length === 0) return Array(binCount - 1).fill(0);
  const sorted = [...values].sort((a, b) => a - b);
  const breaks: number[] = [];
  for (let i = 1; i < binCount; i++) {
    const idx = Math.floor((i / binCount) * sorted.length);
    breaks.push(sorted[Math.min(idx, sorted.length - 1)]);
  }
  return breaks;
}

export function classifyValue(value: number | null, breaks: number[]): number {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) return -1;
  for (let i = 0; i < breaks.length; i++) {
    if (value <= breaks[i]) return i + 1;
  }
  return breaks.length + 1;
}

export function generateClassifiedPalette(
  colorScale: [number, number, number][],
  binCount: number,
): [number, number, number, number][] {
  const palette: [number, number, number, number][] = [NO_DATA_COLOR];
  for (let i = 0; i < binCount; i++) {
    const t = binCount === 1 ? 0.5 : i / (binCount - 1);
    const color = interpolateColor(t, colorScale);
    palette.push([color[0], color[1], color[2], 200]);
  }
  return palette;
}

export function stabilizeViewportBounds(bounds: ViewportBounds): ViewportBounds {
  const snap = (v: number) => Math.round(v * 10) / 10;
  return {
    west: snap(bounds.west),
    east: snap(bounds.east),
    south: snap(bounds.south),
    north: snap(bounds.north),
  };
}
```

- [ ] **Step 6: Run tests to verify all pass**

Run: `cd web && npx vitest run src/lib/__tests__/data.test.ts`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```
feat: add classified color scale engine

computeQuantileBreaks, classifyValue, generateClassifiedPalette,
stabilizeViewportBounds with full test coverage.
```

---

### Task 2: ClassifiedLegend Component

**Files:**
- Create: `web/src/components/ClassifiedLegend.tsx`
- Create: `web/src/components/__tests__/ClassifiedLegend.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `web/src/components/__tests__/ClassifiedLegend.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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
    expect(screen.getByText("Clear")).toBeTruthy();
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
    expect(screen.queryByText("Clear")).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify fail**

Run: `cd web && npx vitest run src/components/__tests__/ClassifiedLegend.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement ClassifiedLegend**

Create `web/src/components/ClassifiedLegend.tsx`:

```tsx
"use client";

import { formatValue, type MetricConfig } from "@/lib/data";

interface ClassifiedLegendProps {
  metric: MetricConfig;
  palette: [number, number, number, number][];
  breaks: number[];
  selectedBins: Set<number>;
  onSelectionChange: (newSelection: Set<number>) => void;
}

function rangeLabel(index: number, breaks: number[], format: MetricConfig["format"]): string {
  if (index === 0) return "N/A";
  const binIdx = index - 1; // palette index → break index
  const lo = binIdx === 0 ? null : breaks[binIdx - 1];
  const hi = binIdx < breaks.length ? breaks[binIdx] : null;
  if (lo === null && hi !== null) return `≤${formatValue(hi, format)}`;
  if (lo !== null && hi === null) return `>${formatValue(lo, format)}`;
  if (lo !== null && hi !== null) return `${formatValue(lo, format)}–${formatValue(hi, format)}`;
  return "";
}

export function ClassifiedLegend({
  metric,
  palette,
  breaks,
  selectedBins,
  onSelectionChange,
}: ClassifiedLegendProps) {
  const handleClick = (binIndex: number) => {
    const next = new Set(selectedBins);
    if (next.has(binIndex)) next.delete(binIndex);
    else next.add(binIndex);
    onSelectionChange(next);
  };

  const handleClear = () => onSelectionChange(new Set());

  // Map palette indices to bin indices: palette[0] → binIndex -1, palette[1] → 1, etc.
  const binIndices = [-1, ...Array.from({ length: palette.length - 1 }, (_, i) => i + 1)];

  return (
    <>
      <div className="mb-1 text-[11px] text-slate-600 dark:text-slate-400">{metric.label}</div>
      <div className="flex items-end gap-0.5">
        {binIndices.map((binIdx, paletteIdx) => {
          const [r, g, b] = palette[paletteIdx];
          const isSelected = selectedBins.has(binIdx);
          const hasSelection = selectedBins.size > 0;
          return (
            <button
              key={binIdx}
              aria-label={`bin ${binIdx}`}
              onClick={() => handleClick(binIdx)}
              className="flex flex-col items-center gap-0.5"
            >
              <div
                className={`h-4 w-5 rounded-sm transition-opacity ${
                  isSelected ? "ring-2 ring-white" : ""
                } ${hasSelection && !isSelected ? "opacity-40" : ""}`}
                style={{ backgroundColor: `rgb(${r},${g},${b})` }}
              />
              <span className="text-[8px] leading-tight text-slate-500 dark:text-slate-500">
                {rangeLabel(paletteIdx, breaks, metric.format)}
              </span>
            </button>
          );
        })}
      </div>
      {selectedBins.size > 0 && (
        <button
          onClick={handleClear}
          className="mt-1 text-[10px] text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
        >
          Clear
        </button>
      )}
    </>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd web && npx vitest run src/components/__tests__/ClassifiedLegend.test.tsx`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat: add ClassifiedLegend component with multi-select swatches
```

---

### Task 3: Update ColorLegend to Route to ClassifiedLegend

**Files:**
- Modify: `web/src/components/ColorLegend.tsx`

- [ ] **Step 1: Update ColorLegend props and routing**

The current `ColorLegend` decides between `GradientLegend` and `BivariateLegend`. Add a third branch for `ClassifiedLegend`.

Add new props to the `ColorLegendProps` interface:

```typescript
import { ClassifiedLegend } from "./ClassifiedLegend";

interface ColorLegendProps {
  primaryMetric: MetricConfig;
  secondaryMetric: MetricConfig | null;
  primaryMinMax: { min: number; max: number };
  secondaryMinMax: { min: number; max: number } | null;
  colorScaleMode: ColorScaleMode;
  onToggleMode: () => void;
  onExitCompare?: () => void;
  granularity: Granularity;
  // New classified props
  quantileBreaks: number[] | null;
  classifiedPalette: [number, number, number, number][] | null;
  selectedBins: Set<number>;
  onSelectionChange: (newSelection: Set<number>) => void;
}
```

- [ ] **Step 2: Update render logic**

In the `ColorLegend` component body, replace the conditional rendering. The logic is:
- If `secondaryMetric` is set → `BivariateLegend` (existing)
- If `quantileBreaks` and `classifiedPalette` are set → `ClassifiedLegend` (new)
- Otherwise → `GradientLegend` (fallback, shouldn't normally happen)

```tsx
const isBivariate = secondaryMetric !== null && secondaryMinMax !== null;
const isClassified = !isBivariate && quantileBreaks !== null && classifiedPalette !== null;

return (
  <div className="rounded-lg border border-slate-200/80 bg-white/90 p-2.5 shadow-md backdrop-blur-sm dark:border-slate-600/80 dark:bg-slate-800/90">
    {isBivariate ? (
      <BivariateLegend primaryMetric={primaryMetric} secondaryMetric={secondaryMetric!} />
    ) : isClassified ? (
      <ClassifiedLegend
        metric={primaryMetric}
        palette={classifiedPalette!}
        breaks={quantileBreaks!}
        selectedBins={selectedBins}
        onSelectionChange={onSelectionChange}
      />
    ) : (
      <GradientLegend metric={primaryMetric} minMax={primaryMinMax} />
    )}
    <div className="mt-1.5 flex items-center gap-2">
      {showToggle && (
        <button
          onClick={onToggleMode}
          className="text-[10px] text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
        >
          Scale: {colorScaleMode === "global" ? "Global" : "Viewport"} ▾
        </button>
      )}
      {isBivariate && onExitCompare && (
        <button
          onClick={onExitCompare}
          className="text-[10px] text-slate-400 hover:text-red-500 dark:text-slate-500"
        >
          ✕ Exit Compare
        </button>
      )}
    </div>
  </div>
);
```

- [ ] **Step 3: Commit**

```
feat: route ColorLegend to ClassifiedLegend for single-metric mode
```

---

### Task 4: Update ChoroplethMap for Classified Colors + Highlights

**Files:**
- Modify: `web/src/components/ChoroplethMap.tsx`

- [ ] **Step 1: Add new props to ChoroplethMapProps**

Add after the existing `secondaryBreaks` prop (~line 63):

```typescript
quantileBreaks: number[] | null;
classifiedPalette: [number, number, number, number][] | null;
highlightedBins: Set<number> | null;
```

Add to the destructured props in the function signature.

- [ ] **Step 2: Import classifyValue and NO_DATA_COLOR**

Update the import from `@/lib/data`:

```typescript
import {
  classifyValue,
  NO_DATA_COLOR,
  // ... existing imports
} from "@/lib/data";
```

- [ ] **Step 3: Replace the single-metric branch in getFillColor**

In `getFillColor` (~line 133-138), replace the single-metric block:

```typescript
// Single-metric mode — classified
if (quantileBreaks && classifiedPalette) {
  const binIdx = classifyValue(primaryVal, quantileBreaks);
  const color = classifiedPalette[binIdx + 1] ?? NO_DATA_COLOR;
  const isHighlighted = !highlightedBins || highlightedBins.size === 0 || highlightedBins.has(binIdx);
  return [color[0], color[1], color[2], isHighlighted ? fillAlpha : 40];
}

// Fallback: continuous interpolation (shouldn't reach here normally)
const range = maxVal - minVal;
const t = range > 0 ? (primaryVal - minVal) / range : 0.5;
const color = interpolateColor(t, metric.colorScale);
color[3] = fillAlpha;
return color;
```

- [ ] **Step 4: Update getLineColor for highlighted bins**

In `getLineColor` (~line 143-157), add highlight stroke logic after the `selectedFips` check:

```typescript
const getLineColor = useCallback(
  (feature: any): [number, number, number, number] => {
    const fips = feature.properties?.GEOID as string | undefined;
    // Selected county: strong outline
    if (fips === selectedFips) {
      return isDark ? [255, 255, 255, 255] : [15, 23, 42, 255];
    }
    // Highlighted bins: white outline
    if (highlightedBins && highlightedBins.size > 0 && quantileBreaks && fips) {
      const county = dataByFips.get(fips);
      if (county) {
        const val = county[metric.key] as number | null;
        const binIdx = classifyValue(val === null ? null : Number(val), quantileBreaks);
        if (highlightedBins.has(binIdx)) {
          return isDark ? [255, 255, 255, 200] : [15, 23, 42, 200];
        }
      }
    }
    if (isBlockGroup) {
      return isDark ? [80, 80, 80, 80] : [148, 163, 184, 80];
    }
    return isDark ? [100, 100, 100, 180] : [148, 163, 184, 180];
  },
  [selectedFips, isDark, isBlockGroup, highlightedBins, quantileBreaks, dataByFips, metric.key],
);
```

- [ ] **Step 5: Add new props to getFillColor dependency array**

Update the dependency array of `getFillColor` to include `quantileBreaks`, `classifiedPalette`, `highlightedBins`.

- [ ] **Step 6: Commit**

```
feat: classified color rendering + bin highlighting in ChoroplethMap
```

---

### Task 5: Redesign ComparisonChart — Layout Flip + Bucket Colors

**Files:**
- Modify: `web/src/components/ComparisonChart.tsx`

- [ ] **Step 1: Update props interface**

Replace `selectedMetro` with new classified props. Remove `colorScaleMode` and `visibleIds` (filtering moved to parent). The full updated interface:

```typescript
interface ComparisonChartProps {
  counties: CountyData[];
  metric: MetricConfig;
  selectedFips: string | null;
  onSelect: (fips: string) => void;
  granularity: Granularity;
  secondaryMetric: MetricConfig | null;
  primaryBreaks: number[] | null;
  secondaryBreaks: number[] | null;
  quantileBreaks: number[] | null;
  classifiedPalette: [number, number, number, number][] | null;
  selectedBins: Set<number>;
}
```

Import `classifyValue` and `NO_DATA_COLOR` from `@/lib/data`.

- [ ] **Step 2: Add bucket filtering logic**

After the existing `sorted` computation, add bucket filtering:

```typescript
const filteredByBucket = selectedBins.size > 0 && quantileBreaks
  ? sorted.filter(c => {
      const val = c[metric.key] as number | null;
      const binIdx = classifyValue(val === null ? null : Number(val), quantileBreaks);
      return selectedBins.has(binIdx);
    })
  : sorted;

const clipped = filteredByBucket.length > 50
  ? filteredByBucket.slice(0, 50)
  : filteredByBucket;
const showingNote = filteredByBucket.length > 50
  ? `Showing 50 of ${filteredByBucket.length} areas`
  : null;
```

Use `clipped` instead of `displayed` for rendering. Show `showingNote` below the bars if set.

- [ ] **Step 3: Update bar color logic**

Replace the single-metric bar color computation. Instead of using the metric's high color for all bars, classify each bar:

```typescript
let barR: number, barG: number, barB: number;
if (isBivariate) {
  // existing bivariate logic unchanged
  const pBin = classifyBin(val, primaryBreaks!);
  const sBin = secVal !== null && !Number.isNaN(secVal) ? classifyBin(secVal, secondaryBreaks!) : 0;
  [barR, barG, barB] = getBivariateColor(pBin, sBin, 255);
} else if (quantileBreaks && classifiedPalette) {
  const binIdx = classifyValue(val, quantileBreaks);
  const color = classifiedPalette[binIdx + 1] ?? NO_DATA_COLOR;
  [barR, barG, barB] = [color[0], color[1], color[2]];
} else {
  [barR, barG, barB] = [defaultR, defaultG, defaultB];
}
```

- [ ] **Step 4: Flip the bar layout**

Change the button contents. Current layout: name right-aligned → bar → value right.
New layout: name left-aligned → bar grows right → value right-aligned.

```tsx
<button
  key={county.county_fips}
  onClick={() => onSelect(county.county_fips)}
  className={`group flex items-center gap-2 rounded px-1 py-0.5 text-left transition-colors ${
    isSelected
      ? "bg-slate-100 dark:bg-slate-800"
      : "hover:bg-slate-100/50 dark:hover:bg-slate-800/50"
  }`}
>
  <span
    className={`${isBlockGroup ? "w-28" : "w-20"} shrink-0 truncate text-xs ${
      isSelected
        ? "font-semibold text-slate-900 dark:text-white"
        : "text-slate-700 dark:text-slate-400"
    }`}
  >
    {nameShort}
  </span>
  <div className="relative h-4 flex-1">
    <div
      className="absolute inset-y-0 left-0 rounded-sm transition-all"
      style={{
        width: `${pct}%`,
        backgroundColor: `rgba(${barR}, ${barG}, ${barB}, ${barOpacity})`,
      }}
    />
  </div>
  <span className="w-18 shrink-0 text-right font-mono text-xs text-slate-700 dark:text-slate-400">
    {formatValue(val, metric.format)}
    {isBivariate && secVal !== null && ` / ${formatValue(secVal, secondaryMetric!.format)}`}
  </span>
</button>
```

Note: the name span changes from `text-right` to no text-right (left-aligned by default). This is the key layout flip.

- [ ] **Step 5: Add showing-note at bottom**

After the bar list, add:

```tsx
{showingNote && (
  <p className="mt-1 text-center text-[10px] text-slate-400 dark:text-slate-500">
    {showingNote}
  </p>
)}
```

- [ ] **Step 6: Update heading to show bucket selection context**

Update the heading logic to indicate when filtering by bucket:

```typescript
const bucketLabel = selectedBins.size > 0 ? ` (${selectedBins.size} bucket${selectedBins.size > 1 ? "s" : ""} selected)` : "";
// ... existing heading logic ...
const heading = isBlockGroup
  ? `${metricLabel}${bucketLabel} — Top/Bottom ${BLOCK_GROUP_LIMIT} ${granLabel}`
  : `${metricLabel}${bucketLabel} — ${metroLabel} ${granLabel}`;
```

- [ ] **Step 7: Commit**

```
feat: flip bar layout, bucket-colored bars, bucket selection filtering
```

---

### Task 6: Wire State in page.tsx

**Files:**
- Modify: `web/src/app/page.tsx`

- [ ] **Step 1: Add imports**

Add to the data imports:

```typescript
import {
  // ... existing ...
  computeQuantileBreaks,
  generateClassifiedPalette,
  stabilizeViewportBounds,
  QUANTILE_BIN_COUNT,
  classifyValue,
} from "@/lib/data";
```

- [ ] **Step 2: Add selectedBins state**

After `const [colorScaleMode, ...]`:

```typescript
const [selectedBins, setSelectedBins] = useState<Set<number>>(new Set());
```

- [ ] **Step 3: Add memoized computations**

After the existing `secondaryBreaks` useMemo, add:

```typescript
const quantileBreaks = useMemo(() => {
  if (secondaryMetric) return null;
  const source = (colorScaleMode === "viewport" && visibleIds)
    ? counties.filter(c => visibleIds.has(c.county_fips))
    : counties;
  const values = source
    .map(c => c[selectedMetric.key] as number | null)
    .filter((v): v is number => v !== null && v !== 0 && Number.isFinite(v));
  return computeQuantileBreaks(values, QUANTILE_BIN_COUNT);
}, [counties, colorScaleMode, visibleIds, selectedMetric.key, secondaryMetric]);

const classifiedPalette = useMemo(() => {
  if (secondaryMetric) return null;
  return generateClassifiedPalette(selectedMetric.colorScale, QUANTILE_BIN_COUNT);
}, [selectedMetric.colorScale, secondaryMetric]);

const displayCounties = useMemo(() => {
  if (colorScaleMode === "viewport" && visibleIds) {
    return counties.filter(c => visibleIds.has(c.county_fips));
  }
  if (selectedMetro) {
    return counties.filter(c => c.metro_id === selectedMetro);
  }
  return counties;
}, [counties, colorScaleMode, visibleIds, selectedMetro]);
```

- [ ] **Step 4: Update viewport stabilization**

Replace `handleViewStateChange` — apply `stabilizeViewportBounds` and increase debounce to 600ms:

```typescript
const handleViewStateChange = useCallback(
  (viewState: Record<string, unknown>) => {
    if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current);
    viewportTimerRef.current = setTimeout(() => {
      const vs = viewState as { longitude: number; latitude: number; zoom: number };
      const span = 360 / Math.pow(2, vs.zoom);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setViewportBounds(stabilizeViewportBounds({
        west: vs.longitude - span / 2,
        east: vs.longitude + span / 2,
        south: vs.latitude - span / 4,
        north: vs.latitude + span / 4,
      }));
    }, 600);
  },
  [],
);
```

- [ ] **Step 5: Add state reset in metric/metro selection handlers**

In the metro selector onChange, add `setSelectedBins(new Set())`.
In the MetricSelector `onSelect` callback, add `setSelectedBins(new Set())`.
In the MetricSelector `onSelectSecondary` callback wrapper, add `setSelectedBins(new Set())`.

- [ ] **Step 6: Wire new props to ChoroplethMap**

Add to the `<ChoroplethMap>` JSX:

```tsx
quantileBreaks={quantileBreaks}
classifiedPalette={classifiedPalette}
highlightedBins={selectedBins.size > 0 ? selectedBins : null}
```

- [ ] **Step 7: Wire new props to ColorLegend**

Add to the `<ColorLegend>` JSX:

```tsx
quantileBreaks={quantileBreaks}
classifiedPalette={classifiedPalette}
selectedBins={selectedBins}
onSelectionChange={setSelectedBins}
```

- [ ] **Step 8: Wire new props to ComparisonChart**

Update `<ComparisonChart>`. Replace `selectedMetro` prop with new classified props. Pass `displayCounties` instead of `counties`:

```tsx
<ComparisonChart
  counties={displayCounties}
  metric={selectedMetric}
  selectedFips={selectedFips}
  onSelect={setSelectedFips}
  granularity={granularity}
  secondaryMetric={secondaryMetric}
  primaryBreaks={primaryBreaks}
  secondaryBreaks={secondaryBreaks}
  quantileBreaks={quantileBreaks}
  classifiedPalette={classifiedPalette}
  selectedBins={selectedBins}
/>
```

- [ ] **Step 9: Commit**

```
feat: wire classified color scale state through page.tsx
```

---

### Task 7: Build Verification + Lint

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

Run: `cd web && npx vitest run`
Expected: ALL PASS

- [ ] **Step 2: Run lint**

Run: `cd web && npm run lint`
Expected: Zero errors, zero warnings. If new eslint-disable comments needed, add with explanatory text.

- [ ] **Step 3: Run production build**

Run: `cd web && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 4: Start dev server and validate visually**

Ask the user to run `! cd web && npm run dev`. Then use `/chrome-devtools` to verify:

1. Map shows 5 discrete colors + gray for no-data
2. Legend shows 6 clickable swatches with range labels
3. Clicking a swatch highlights matching areas (white outline, others fade)
4. Multi-select works (click additional swatches)
5. "Clear" button appears on selection, resets on click
6. Bottom panel bars are colored by their bucket
7. Bar layout: name left, bar right, value right
8. Selecting a bucket → bars filter to that bucket's areas
9. Scale: Viewport → colors stable during small pans
10. Quick Combos still show 3×3 bivariate grid (no regression)
11. Mobile layout still works

- [ ] **Step 5: Commit any fixes from validation**

---

## Success Criteria

| Requirement | Pass condition |
|---|---|
| Classified colors | Map shows 5 discrete colors + 1 no-data gray |
| Stable viewport | Small pans (< 0.1°) produce no color changes |
| Legend interaction | Click swatch → highlights matching areas; multi-select works |
| Highlight rendering | Selected bins: white outline + full alpha; others: 40% alpha |
| Bar layout | Name left, bar rightward, value right-aligned |
| Bucket-colored bars | Each bar matches its map color |
| Bucket filter | Selected bucket → shows matching areas sorted descending |
| Bivariate preserved | Quick Combos still use 3×3 grid |
| Performance | No lag for 50 counties or 4,400 block groups |
| Tests | All unit + component tests pass |
| Lint | Zero errors, zero warnings |
| Build | `npm run build` succeeds |
