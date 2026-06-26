"use client";

import {
  formatValue,
  classifyBin,
  classifyValue,
  BIVARIATE_PALETTE,
  QUANTILE_BIN_COUNT,
  PERCENTILE_LABELS,
  type CountyData,
  type Granularity,
  type MetricConfig,
} from "@/lib/data";
import { METROS } from "@/lib/metro";

const BLOCK_GROUP_LIMIT = 20;

type RowItem = {
  type: "area";
  county: CountyData;
  val: number;
  binIdx: number;
} | {
  type: "aggregate";
  binIdx: number;
  count: number;
  avg: number;
};

function limitBlockGroups(items: CountyData[]): CountyData[] {
  if (items.length <= BLOCK_GROUP_LIMIT * 2) return items;
  return [...items.slice(0, BLOCK_GROUP_LIMIT), ...items.slice(-BLOCK_GROUP_LIMIT)]
    .filter((v, i, arr) => arr.findIndex((c) => c.county_fips === v.county_fips) === i);
}

function sortRows(aggregates: RowItem[], individuals: RowItem[]): RowItem[] {
  return [...aggregates, ...individuals].sort((a, b) => {
    const aVal = a.type === "aggregate" ? a.avg : a.val;
    const bVal = b.type === "aggregate" ? b.avg : b.val;
    return bVal - aVal;
  });
}

interface ComparisonChartProps {
  counties: CountyData[];
  metric: MetricConfig;
  selectedFips: string | null;
  onSelect: (fips: string) => void;
  granularity: Granularity;
  secondaryMetric: MetricConfig | null;
  primaryBreaks: number[] | null;
  secondaryBreaks: number[] | null;
  selectedMetro: string | null;
  quantileBreaks?: number[] | null;
  classifiedPalette?: [number, number, number, number][] | null;
  selectedBins?: Set<number>;
  bivariatePalette?: [number, number, number][][] | null;
  selectedBivariateCell?: { row: number; col: number } | null;
}

export function ComparisonChart({
  counties,
  metric,
  selectedFips,
  onSelect,
  granularity,
  secondaryMetric,
  primaryBreaks,
  secondaryBreaks,
  selectedMetro,
  quantileBreaks = null,
  classifiedPalette = null,
  selectedBins = new Set<number>(),
  bivariatePalette = null,
  selectedBivariateCell = null,
}: ComparisonChartProps) {
  if (granularity === "metro" && counties.length <= 1) {
    return (
      <div className="p-3 text-center text-sm text-slate-400 dark:text-slate-500">
        Metro view shows aggregate data — no comparison available.
      </div>
    );
  }

  const withData = counties.filter((c) => {
    const v = c[metric.key];
    return v !== null && v !== undefined && !Number.isNaN(v as number);
  });
  const sorted = [...withData].sort(
    (a, b) => ((b[metric.key] as number) ?? 0) - ((a[metric.key] as number) ?? 0),
  );

  const isBlockGroup = granularity === "block_group";
  const isBivariate = secondaryMetric !== null && primaryBreaks !== null && secondaryBreaks !== null;
  const activePalette = bivariatePalette ?? BIVARIATE_PALETTE;

  const metroLabel = selectedMetro && granularity === "county"
    ? METROS[selectedMetro]?.metro_name.split(" MSA")[0] ?? "Selected Metro"
    : "All";
  const granLabel = granularity === "metro" ? "Metro Areas" : isBlockGroup ? "Block Groups" : "Counties";
  const bucketLabel = selectedBins.size > 0 ? ` (${selectedBins.size} bucket${selectedBins.size > 1 ? "s" : ""} selected)` : "";
  const heading = isBlockGroup
    ? `${metric.label}${isBivariate ? ` × ${secondaryMetric!.label}` : ""}${bucketLabel} — Top/Bottom ${BLOCK_GROUP_LIMIT} ${granLabel}`
    : `${metric.label}${isBivariate ? ` × ${secondaryMetric!.label}` : ""}${bucketLabel} — ${metroLabel} ${granLabel}`;

  const shortenName = (county: CountyData): string => {
    if (isBlockGroup) {
      const parts = county.county_name.split(";");
      const countyPart = parts.length >= 3 ? parts[2].trim().replace(/ County$/, "") : "";
      const fipsSuffix = county.county_fips.slice(-4);
      return countyPart ? `${countyPart} ${fipsSuffix}` : county.county_fips;
    }
    return county.county_name.replace(/ County,.*$/, "");
  };

  const getBarColor = (county: CountyData, val: number): [number, number, number] => {
    if (isBivariate) {
      const secVal = county[secondaryMetric!.key] as number | null;
      const pBin = classifyBin(val, primaryBreaks!);
      const sBin = secVal !== null && !Number.isNaN(secVal) ? classifyBin(secVal, secondaryBreaks!) : 0;
      const row = Math.max(0, Math.min(2, pBin));
      const col = Math.max(0, Math.min(2, sBin));
      return activePalette[row][col];
    }
    if (quantileBreaks && classifiedPalette) {
      const binIdx = classifyValue(val, quantileBreaks);
      const paletteIdx = binIdx === -1 ? 0 : binIdx;
      const color = classifiedPalette[paletteIdx];
      return [color[0], color[1], color[2]];
    }
    return metric.colorScale[metric.colorScale.length - 1];
  };

  // Build row list
  const useBucketMode = selectedBins.size > 0 && quantileBreaks !== null && classifiedPalette !== null;

  let rows: RowItem[];
  if (useBucketMode) {
    const binGroups = new Map<number, CountyData[]>();
    for (const c of sorted) {
      const val = c[metric.key] as number | null;
      const bi = classifyValue(val, quantileBreaks!);
      const group = binGroups.get(bi) ?? [];
      group.push(c);
      binGroups.set(bi, group);
    }

    const aggregates: RowItem[] = [];
    const individuals: RowItem[] = [];
    for (let bi = 1; bi <= QUANTILE_BIN_COUNT; bi++) {
      const group = binGroups.get(bi) ?? [];
      if (group.length === 0) continue;
      const sum = group.reduce((acc, c) => acc + ((c[metric.key] as number) ?? 0), 0);
      const avg = sum / group.length;
      if (selectedBins.has(bi)) {
        const displayed = isBlockGroup ? limitBlockGroups(group) : group;
        for (const c of displayed) {
          individuals.push({ type: "area", county: c, val: (c[metric.key] as number) ?? 0, binIdx: bi });
        }
      } else {
        aggregates.push({ type: "aggregate", binIdx: bi, count: group.length, avg });
      }
    }
    const naGroup = binGroups.get(-1) ?? [];
    if (naGroup.length > 0 && !selectedBins.has(-1)) {
      const naSum = naGroup.reduce((acc, c) => acc + ((c[metric.key] as number) ?? 0), 0);
      aggregates.push({ type: "aggregate", binIdx: -1, count: naGroup.length, avg: naSum / naGroup.length });
    }
    rows = sortRows(aggregates, individuals);
  } else if (selectedBivariateCell && isBivariate) {
    const cellGroups = new Map<string, CountyData[]>();
    for (const c of sorted) {
      const pVal = (c[metric.key] as number) ?? 0;
      const sVal = c[secondaryMetric!.key] as number | null;
      const pBin = classifyBin(pVal, primaryBreaks!);
      const sBin = sVal !== null && !Number.isNaN(sVal) ? classifyBin(sVal, secondaryBreaks!) : 0;
      const row = Math.max(0, Math.min(2, pBin));
      const col = Math.max(0, Math.min(2, sBin));
      const group = cellGroups.get(`${row}-${col}`) ?? [];
      group.push(c);
      cellGroups.set(`${row}-${col}`, group);
    }

    const aggregates: RowItem[] = [];
    const individuals: RowItem[] = [];
    for (let ri = 0; ri < 3; ri++) {
      for (let ci = 0; ci < 3; ci++) {
        const group = cellGroups.get(`${ri}-${ci}`) ?? [];
        if (group.length === 0) continue;
        const sum = group.reduce((acc, c) => acc + ((c[metric.key] as number) ?? 0), 0);
        const avg = sum / group.length;
        if (ri === selectedBivariateCell.row && ci === selectedBivariateCell.col) {
          const displayed = isBlockGroup ? limitBlockGroups(group) : group;
          for (const c of displayed) {
            individuals.push({ type: "area", county: c, val: (c[metric.key] as number) ?? 0, binIdx: ri * 3 + ci });
          }
        } else {
          aggregates.push({ type: "aggregate", binIdx: ri * 3 + ci, count: group.length, avg });
        }
      }
    }
    rows = sortRows(aggregates, individuals);
  } else {
    const limited = isBlockGroup ? limitBlockGroups(sorted) : sorted;
    const MAX_DISPLAY = 50;
    const clipped = limited.length > MAX_DISPLAY ? limited.slice(0, MAX_DISPLAY) : limited;
    rows = clipped.map(c => ({
      type: "area",
      county: c,
      val: (c[metric.key] as number) ?? 0,
      binIdx: quantileBreaks ? classifyValue((c[metric.key] as number) ?? 0, quantileBreaks) : 0,
    }));
  }

  let maxVal = 0;
  for (const r of rows) {
    const v = r.type === "area" ? r.val : r.avg;
    if (v > maxVal) maxVal = v;
  }

  return (
    <div className="p-3">
      <h3 className="mb-2 text-xs font-semibold tracking-wider text-slate-600 uppercase dark:text-slate-500">
        {heading}
      </h3>
      <div className="flex flex-col gap-0.5">
        {rows.map((row, idx) => {
          if (row.type === "aggregate") {
            let r: number, g: number, b: number;
            let label: string;
            const cellLabels = ["Low", "Mid", "High"];
            if (isBivariate && row.binIdx >= 0) {
              const ri = Math.floor(row.binIdx / 3);
              const ci = row.binIdx % 3;
              [r, g, b] = activePalette[ri]?.[ci] ?? [150, 150, 150];
              label = `${cellLabels[ri]}×${cellLabels[ci]}`;
            } else if (classifiedPalette) {
              const paletteIdx = row.binIdx === -1 ? 0 : row.binIdx;
              const color = classifiedPalette[paletteIdx];
              [r, g, b] = [color[0], color[1], color[2]];
              label = PERCENTILE_LABELS[row.binIdx === -1 ? 0 : row.binIdx] ?? `Bin ${row.binIdx}`;
            } else {
              [r, g, b] = [150, 150, 150];
              label = `Bin ${row.binIdx}`;
            }
            const avgPct = maxVal > 0 ? (row.avg / maxVal) * 100 : 0;
            return (
              <div key={`agg-${row.binIdx}`} className="flex items-center gap-2 rounded px-1 py-0.5">
                <span className="w-28 shrink-0 truncate whitespace-nowrap text-left text-xs text-slate-500 dark:text-slate-400">
                  {label} ({row.count})
                </span>
                <div className="relative h-3 flex-1">
                  <div
                    className="absolute inset-y-0 left-0 rounded-sm"
                    style={{ width: `${avgPct}%`, backgroundColor: `rgba(${r},${g},${b},0.7)` }}
                  />
                </div>
                <span className="w-24 shrink-0 whitespace-nowrap text-right font-mono text-xs text-slate-400 dark:text-slate-500">
                  {formatValue(row.avg, metric.format)} avg
                </span>
              </div>
            );
          }

          const { county, val } = row;
          const pct = maxVal > 0 ? (val / maxVal) * 100 : 0;
          const isSelected = county.county_fips === selectedFips;
          const [barR, barG, barB] = getBarColor(county, val);
          const secVal = isBivariate ? (county[secondaryMetric!.key] as number | null) : null;

          return (
            <button
              key={`${county.county_fips}-${idx}`}
              onClick={() => onSelect(county.county_fips)}
              className={`group flex items-center gap-2 rounded px-1 py-0.5 text-left transition-colors ${
                isSelected ? "bg-slate-100 dark:bg-slate-800" : "hover:bg-slate-100/50 dark:hover:bg-slate-800/50"
              }`}
            >
              <span
                className={`w-28 shrink-0 truncate whitespace-nowrap text-left text-xs ${
                  isSelected ? "font-semibold text-slate-900 dark:text-white" : "text-slate-700 dark:text-slate-400"
                }`}
              >
                {shortenName(county)}
              </span>
              <div className="relative h-4 flex-1">
                <div
                  className="absolute inset-y-0 left-0 rounded-sm transition-all"
                  style={{ width: `${pct}%`, backgroundColor: `rgba(${barR}, ${barG}, ${barB}, ${isSelected ? 1 : 0.85})` }}
                />
              </div>
              <span className="w-24 shrink-0 whitespace-nowrap text-right font-mono text-xs text-slate-700 dark:text-slate-400">
                {formatValue(val, metric.format)}
                {isBivariate && secVal !== null && ` / ${formatValue(secVal, secondaryMetric!.format)}`}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
