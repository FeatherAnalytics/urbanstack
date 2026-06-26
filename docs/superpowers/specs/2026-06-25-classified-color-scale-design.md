# Classified Color Scale — Design Specification

## Goal

Replace the continuous gradient choropleth with a classified (quantile bucket) color scale that makes spatial patterns more readable, enables interactive bucket selection with map highlighting, and provides distribution context through a redesigned bottom panel.

## Architecture

The color pipeline changes from `normalize → interpolate` to `classify → lookup`. Quantile breaks divide values into 5 equal-count bins. Each bin gets a discrete color sampled from the metric's existing color ramp. One additional color handles missing/null/zero data. The classification engine, legend, map rendering, and bottom panel are independent modules connected through shared state in `page.tsx`.

## Scope

**In scope:**
- Classified color engine (5 quantile bins + 1 no-data state)
- Clickable legend with multi-select bucket highlighting
- Map highlight rendering for selected buckets
- Bottom panel: flipped bar layout, bucket-colored bars, filtered view on selection
- Viewport bounds stabilization (rounding + debounce)
- Global/viewport mode preserved with stable behavior

**Out of scope (future work):**
- Metric sidebar redesign
- Scatter plot for bivariate bucket selection
- Animated transitions on bucket selection beyond CSS fade

---

## 1. Color Classification Engine

### Current behavior

`interpolateColor(t, stops)` maps a 0–1 normalized value to a continuous RGB gradient. Each `MetricConfig` has a `colorScale: [number, number, number][]` with 3 stops (low, mid, high). The `computeDisplayRange` function returns p10/p90 as min/max, and the map normalizes each value into that range.

### New behavior

A quantile classification pipeline replaces continuous interpolation for single-metric mode. Bivariate mode (Quick Combos) retains its existing 3×3 classification unchanged.

### Constants

```typescript
export const QUANTILE_BIN_COUNT = 5;
export const NO_DATA_COLOR: [number, number, number, number] = [200, 200, 200, 80];
```

### Functions (all in `data.ts`, all exported)

**`computeQuantileBreaks(values: number[], binCount: number): number[]`**

Extends the existing `computeQuantileBins` (which is hardcoded for bivariate 3-class). Returns `binCount - 1` breakpoints dividing sorted values into `binCount` equal-count groups.

- Input: array of finite, non-null, non-zero metric values; desired bin count
- Output: array of breakpoints (e.g., for 5 bins → 4 breakpoints)
- Edge cases:
  - Empty array → all breaks = 0
  - Fewer values than bins → some bins may be empty; breaks deduplicate
  - All values identical → all breaks equal that value; all areas land in bin 1

**`classifyValue(value: number | null, breaks: number[]): number`**

Returns the bin index for a given value.

- Returns -1 if value is null, undefined, NaN, or zero (no-data state)
- Returns 1–5 for quantile bins (1 = lowest quintile, 5 = highest)
- Linear search through breaks (4 comparisons max)
- Value exactly on a break boundary → assigned to the lower bin (≤ break)

Total: 6 possible return values (-1, 1, 2, 3, 4, 5). The palette array maps these to colors.

**`generateClassifiedPalette(colorScale: [number, number, number][], binCount: number): [number, number, number, number][]`**

Samples `binCount` colors from the metric's existing 3-stop color ramp at evenly spaced positions. Returns a flat array indexed by `binIndex + 1`:

- Index 0 (binIndex -1) → `NO_DATA_COLOR` (light gray, low opacity)
- Indices 1–5 (binIndex 1–5) → sampled from `colorScale` at positions 0%, 25%, 50%, 75%, 100%

Array access: `palette[binIndex + 1]`. Total length: `binCount + 1` (6 entries for 5 bins).

Uses the existing `interpolateColor` function internally to sample the ramp.

**`stabilizeViewportBounds(bounds: ViewportBounds): ViewportBounds`**

Rounds each bound (west, east, south, north) to 0.1° precision. Prevents sub-pixel pans from changing the visible county set.

```typescript
function stabilizeViewportBounds(bounds: ViewportBounds): ViewportBounds {
  const snap = (v: number) => Math.round(v * 10) / 10;
  return { west: snap(bounds.west), east: snap(bounds.east), south: snap(bounds.south), north: snap(bounds.north) };
}
```

### MetricConfig changes

None. The existing `colorScale` (3 RGB stops) is the source for generating the 5-step classified palette.

### Relationship to bivariate mode

Bivariate mode (Quick Combos) continues using its own pipeline: `computeQuantileBins(values, 3)` → `classifyBin` → `getBivariateColor` from `BIVARIATE_PALETTE`. The classified scale applies only to single-metric mode. The two systems are independent — switching between them is handled by the existing `secondaryMetric` state.

---

## 2. Map Rendering

### Current behavior

`ChoroplethMap.getFillColor` has two branches:
- Single-metric: `t = (val - minVal) / (maxVal - minVal)` → `interpolateColor(t, colorScale)` → continuous RGBA
- Bivariate: `classifyBin(val, breaks)` → `getBivariateColor(pBin, sBin, alpha)` → discrete RGBA

### New behavior

Single-metric branch switches to classification:
- `classifyValue(val, quantileBreaks)` → bin index → `palette[binIndex + 1]` → discrete RGBA
- Bivariate branch unchanged
- Fallback: if palette lookup returns undefined, use `NO_DATA_COLOR`

### New props on ChoroplethMap

```typescript
quantileBreaks: number[] | null;                          // null = bivariate mode
classifiedPalette: [number, number, number, number][] | null;
highlightedBins: Set<number> | null;                      // which bins are selected in legend
```

### Highlight rendering

When `highlightedBins` is non-null and non-empty:
- Features whose bin index is IN the set: full alpha (200) + white stroke (2px)
- Features whose bin index is NOT in the set: reduced alpha (40) + no stroke change
- This is purely a rendering change in `getFillColor` and `getLineColor` — no data filtering

When `highlightedBins` is null or empty: all features render at normal alpha. Same as today.

### Performance

`classifyValue` is 4 comparisons per feature (vs current division + multi-step interpolation). Breaks and palette are computed once per metric/viewport change, passed as props, not recomputed per feature. Highlight toggling is O(1) — just a Set.has() check in getFillColor.

---

## 3. Legend Component

### Current behavior

`ColorLegend` renders either:
- `GradientLegend`: CSS linear gradient bar with min/max labels
- `BivariateLegend`: 3×3 color grid with axis labels

### New behavior

Replace `GradientLegend` with `ClassifiedLegend` for single-metric mode. `BivariateLegend` unchanged.

### ClassifiedLegend component

**Props:**
```typescript
interface ClassifiedLegendProps {
  metric: MetricConfig;
  palette: [number, number, number, number][];
  breaks: number[];
  selectedBins: Set<number>;
  onSelectionChange: (newSelection: Set<number>) => void;
}
```

**Layout (desktop and mobile — same):**
- Horizontal row of 6 color swatches (~22×16px each)
- Below each swatch: value range label (e.g., "N/A", "0–23K", "23K–87K", ..., "400K+")
- Selected swatches get a white ring border (2px)
- "Clear" text button appears when any bin is selected

**Interaction:**
- Click swatch → toggles bin in `selectedBins` set via `onSelectionChange`
- Multi-select supported (click additional swatches)
- Click selected swatch again → deselects it
- "Clear" button → calls `onSelectionChange(new Set())`

### Scale mode toggle

The "Scale: Global ▾" / "Scale: Viewport ▾" toggle button remains below the legend. It controls whether quantile breaks are computed from all data or viewport-visible data. With classified bins, visual stability is much better than continuous gradients — colors only change when a county crosses a bin boundary during pan.

---

## 4. Bottom Panel (ComparisonChart)

### Current behavior

Horizontal bar chart: county name right-aligned, bar grows right, value at far right. Single color per bar (metric's "high" color). Bars sorted descending by metric value. Filters by selected metro.

### New behavior — Normal mode (no bins selected)

**Layout flipped:**
- County/area name: left-aligned
- Bar: grows rightward
- Value: right-aligned at the end of the row

**Bar colors:** Each bar colored by its quantile bucket (matching map colors). Uses same `classifyValue` + `palette` as the map.

**Filtering logic — determined by parent (page.tsx), not ComparisonChart:**
- Viewport mode → pass only counties visible in current viewport
- Global mode + metro selected → pass that metro's counties
- Global mode + All US → pass all counties

ComparisonChart receives a pre-filtered `counties` array. No filtering logic inside the component.

### New behavior — Bucket selection mode (legend swatches selected)

When `selectedBins` is non-empty, the bottom panel filters to selected areas:

```typescript
const filteredByBucket = selectedBins.size > 0
  ? sorted.filter(c => {
      const val = c[metric.key] as number | null;
      const binIndex = classifyValue(val, quantileBreaks);
      return selectedBins.has(binIndex);
    })
  : sorted;
```

- Shows all areas in the selected bucket(s) as individual bars, sorted descending
- If more than 50 areas, shows top 50 with a note "Showing 50 of N areas"
- Clicking an area name still selects it on the map (opens county detail)

### Bivariate mode

When a Quick Combo is active, the bar chart continues using bivariate colors from the existing `getBivariateColor` pipeline. Bucket selection from the classified legend is not available in bivariate mode (the legend shows the 3×3 grid instead).

### Props changes on ComparisonChart

Remove `colorScaleMode` and `visibleIds` (filtering moves to parent). Add:

```typescript
quantileBreaks: number[] | null;
classifiedPalette: [number, number, number, number][] | null;
selectedBins: Set<number>;
```

---

## 5. State Management

### New state in page.tsx

```typescript
const [selectedBins, setSelectedBins] = useState<Set<number>>(new Set());
```

Initial state is empty Set (no selection), not null. Null would mean "feature disabled."

### Memoized computations in page.tsx

```typescript
// Quantile breaks — recomputes when data, metric, scale mode, or visible set changes
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

// Palette — recomputes only when metric changes (color ramp is per-metric)
const classifiedPalette = useMemo(() => {
  if (secondaryMetric) return null;
  return generateClassifiedPalette(selectedMetric.colorScale, QUANTILE_BIN_COUNT);
}, [selectedMetric.colorScale, secondaryMetric]);

// Pre-filtered counties for ComparisonChart
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

### Viewport bounds stabilization

In `handleViewStateChange`, apply rounding before setting bounds and increase debounce:

```typescript
const handleViewStateChange = useCallback((viewState: Record<string, unknown>) => {
  if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current);
  viewportTimerRef.current = setTimeout(() => {
    const vs = viewState as { longitude: number; latitude: number; zoom: number };
    const span = 360 / Math.pow(2, vs.zoom);
    setViewportBounds(stabilizeViewportBounds({
      west: vs.longitude - span / 2,
      east: vs.longitude + span / 2,
      south: vs.latitude - span / 4,
      north: vs.latitude + span / 4,
    }));
  }, 600);
}, []);
```

### What recomputes when

| User action | State change | Recomputes |
|---|---|---|
| Pan/zoom map | viewportBounds → visibleIds | quantileBreaks (viewport mode only), displayCounties |
| Switch metric | selectedMetric | quantileBreaks + classifiedPalette, clear selectedBins |
| Switch metro | counties reload | quantileBreaks + displayCounties, clear selectedBins |
| Click legend swatch | selectedBins | Nothing (O(1) Set toggle) |
| Toggle global/viewport | colorScaleMode → visibleIds | quantileBreaks + displayCounties |
| Switch to bivariate | secondaryMetric set | quantileBreaks/palette → null, clear selectedBins |

### State reset rules

- Switching metric → clear `selectedBins`
- Switching metro → clear `selectedBins`
- Switching to bivariate → clear `selectedBins` (legend changes to 3×3 grid)
- Panning map → `selectedBins` preserved (highlighted areas stay highlighted)

---

## 6. Testing

### Unit tests (data.ts)

**computeQuantileBreaks:**
- 10 values, 5 bins → 4 breakpoints at 20/40/60/80th percentile positions
- Empty array → all breaks = 0
- All identical values → all breaks equal; all areas classify into bin 1
- Fewer values than bins → handles gracefully (no crash)
- Already sorted vs unsorted input → same result

**classifyValue:**
- Value in each bin → returns correct index (1–5)
- Null → returns -1
- Zero → returns -1
- NaN → returns -1
- Value exactly on a break boundary → assigned to lower bin (≤ break → lower)
- All breaks identical → all values classify into bin 1

**generateClassifiedPalette:**
- Returns array with 6 entries (1 no-data + 5 quantile)
- Colors for bins 1–5 match samples from the input color ramp
- Index 0 is `NO_DATA_COLOR`

**stabilizeViewportBounds:**
- Rounds to 0.1° precision
- Small perturbation (±0.04°) → same output
- Large movement (±0.1°) → different output

### Component tests

**ClassifiedLegend:**
- Renders 6 swatches
- Click toggles bin via `onSelectionChange`
- Selected swatches have ring border
- Clear button appears when selection non-empty

**ComparisonChart (updated):**
- Bars colored by quantile bucket
- Name left-aligned, value right-aligned
- Bucket selection → filters to selected areas

---

## 7. File Structure

| File | Changes | Exports |
|------|---------|---------|
| `web/src/lib/data.ts` | Add 4 functions + 2 constants | `computeQuantileBreaks`, `classifyValue`, `generateClassifiedPalette`, `stabilizeViewportBounds`, `QUANTILE_BIN_COUNT`, `NO_DATA_COLOR` |
| `web/src/lib/__tests__/data.test.ts` | Add tests for all new functions | — |
| `web/src/components/ClassifiedLegend.tsx` | New component | `ClassifiedLegend` |
| `web/src/components/__tests__/ClassifiedLegend.test.tsx` | New test file | — |
| `web/src/components/ColorLegend.tsx` | Modify to delegate to ClassifiedLegend or BivariateLegend | — |
| `web/src/components/ChoroplethMap.tsx` | Modify getFillColor for classified + highlight | — |
| `web/src/components/ComparisonChart.tsx` | Flip layout, add bucket coloring, accept pre-filtered data | — |
| `web/src/app/page.tsx` | Add state, memoized breaks/palette/displayCounties, wire props, viewport stabilization | — |

---

## Success Criteria

| Requirement | Pass condition |
|---|---|
| Classified colors | Map shows 5 discrete colors per metric + 1 no-data gray, not a continuous gradient |
| Stable viewport mode | Small pans (< 0.1°) produce no color/scale changes when no counties enter/leave viewport |
| Legend interaction | Clicking a swatch highlights all matching areas on the map; multi-select works |
| Highlight rendering | Selected-bin areas get white outline + full opacity; others fade to 40% |
| Bottom panel layout | Name left-aligned, bar grows rightward, value right-aligned |
| Bucket-colored bars | Each bar matches its map color |
| Bucket selection filter | Selected bucket → shows all matching areas sorted descending |
| Bar chart filtering | Viewport mode shows visible; global + metro shows metro; global shows all |
| Bivariate preserved | Quick Combos still use 3×3 grid, unaffected by classified scale |
| Performance | No perceptible lag on metric switch or bucket selection for 50 counties or 4,400 block groups |
| Tests pass | All new unit + component tests pass |
| Lint clean | Zero errors, zero warnings |
| Build succeeds | `npm run build` produces valid static export |
