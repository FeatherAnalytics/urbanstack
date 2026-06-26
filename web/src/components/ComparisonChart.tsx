"use client";

import {
  formatValue,
  classifyBin,
  classifyValue,
  getBivariateColor,
  NO_DATA_COLOR,
  type CountyData,
  type Granularity,
  type MetricConfig,
} from "@/lib/data";
import { METROS } from "@/lib/metro";

const BLOCK_GROUP_LIMIT = 20;

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
}: ComparisonChartProps) {
  if (granularity === "metro" && counties.length <= 1) {
    return (
      <div className="p-3 text-center text-sm text-slate-400 dark:text-slate-500">
        Metro view shows aggregate data — no comparison available.
      </div>
    );
  }

  const filteredCounties = selectedMetro && granularity === "county"
    ? counties.filter((c) => c.metro_id === selectedMetro)
    : counties;

  const withData = filteredCounties.filter((c) => {
    const v = c[metric.key];
    return v !== null && v !== undefined && !Number.isNaN(v as number);
  });
  const sorted = [...withData].sort(
    (a, b) => ((b[metric.key] as number) ?? 0) - ((a[metric.key] as number) ?? 0),
  );

  const filteredByBucket = selectedBins.size > 0 && quantileBreaks
    ? sorted.filter(c => {
        const val = c[metric.key] as number | null;
        const binIdx = classifyValue(val === null ? null : Number(val), quantileBreaks);
        return selectedBins.has(binIdx);
      })
    : sorted;

  const isBlockGroup = granularity === "block_group";
  const displayedPreLimit = isBlockGroup
    ? [
        ...filteredByBucket.slice(0, BLOCK_GROUP_LIMIT),
        ...filteredByBucket.slice(-BLOCK_GROUP_LIMIT),
      ].filter((v, i, arr) => arr.findIndex((c) => c.county_fips === v.county_fips) === i)
    : filteredByBucket;

  const MAX_DISPLAY = 50;
  const clipped = displayedPreLimit.length > MAX_DISPLAY
    ? displayedPreLimit.slice(0, MAX_DISPLAY)
    : displayedPreLimit;
  const showingNote = displayedPreLimit.length > MAX_DISPLAY
    ? `Showing ${MAX_DISPLAY} of ${displayedPreLimit.length} areas`
    : null;

  let maxVal = 0;
  for (const c of sorted) {
    const v = (c[metric.key] as number) ?? 0;
    if (v > maxVal) maxVal = v;
  }

  const isBivariate = secondaryMetric !== null && primaryBreaks !== null && secondaryBreaks !== null;
  const [defaultR, defaultG, defaultB] = metric.colorScale[metric.colorScale.length - 1];

  const metroLabel = selectedMetro && granularity === "county"
    ? METROS[selectedMetro]?.metro_name.split(" MSA")[0] ?? "Selected Metro"
    : "All";

  const granLabel = granularity === "metro" ? "Metro Areas" : isBlockGroup ? "Block Groups" : "Counties";

  const bucketLabel = selectedBins.size > 0 ? ` (${selectedBins.size} bucket${selectedBins.size > 1 ? "s" : ""} selected)` : "";

  const heading = isBlockGroup
    ? `${metric.label}${isBivariate ? ` × ${secondaryMetric!.label}` : ""}${bucketLabel} — Top/Bottom ${BLOCK_GROUP_LIMIT} ${granLabel}`
    : `${metric.label}${isBivariate ? ` × ${secondaryMetric!.label}` : ""}${bucketLabel} — ${metroLabel} ${granLabel}`;

  return (
    <div className="p-3">
      <h3 className="mb-2 text-xs font-semibold tracking-wider text-slate-600 uppercase dark:text-slate-500">
        {heading}
      </h3>
      <div className="flex flex-col gap-1">
        {clipped.map((county) => {
          const val = (county[metric.key] as number) ?? 0;
          const pct = maxVal > 0 ? (val / maxVal) * 100 : 0;
          const isSelected = county.county_fips === selectedFips;

          const secVal = isBivariate ? (county[secondaryMetric!.key] as number | null) : null;
          let barR: number, barG: number, barB: number;
          if (isBivariate) {
            const pBin = classifyBin(val, primaryBreaks!);
            const sBin = secVal !== null && !Number.isNaN(secVal) ? classifyBin(secVal, secondaryBreaks!) : 0;
            [barR, barG, barB] = getBivariateColor(pBin, sBin, 255);
          } else if (quantileBreaks && classifiedPalette) {
            const binIdx = classifyValue(val, quantileBreaks);
            const paletteIdx = binIdx === -1 ? 0 : binIdx;
            const color = classifiedPalette[paletteIdx] ?? NO_DATA_COLOR;
            [barR, barG, barB] = [color[0], color[1], color[2]];
          } else {
            [barR, barG, barB] = [defaultR, defaultG, defaultB];
          }

          const barOpacity = isSelected ? 1 : 0.6;
          let nameShort: string;
          if (isBlockGroup) {
            // county_name format: "Block Group 1; Census Tract 301.01; Collin County; Texas"
            const parts = county.county_name.split(";");
            const countyPart = parts.length >= 3
              ? parts[2].trim().replace(/ County$/, "")
              : "";
            const fipsSuffix = county.county_fips.slice(-4);
            nameShort = countyPart ? `${countyPart} ${fipsSuffix}` : county.county_fips;
          } else {
            nameShort = county.county_name.replace(/ County,.*$/, "");
          }

          return (
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
                className={`${isBlockGroup ? "w-28" : "w-20"} shrink-0 text-left text-xs ${
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
          );
        })}
      </div>
      {showingNote && (
        <p className="mt-1 text-center text-[10px] text-slate-400 dark:text-slate-500">
          {showingNote}
        </p>
      )}
    </div>
  );
}
