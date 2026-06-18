"use client";

import { formatValue, type CountyData, type Granularity, type MetricConfig } from "@/lib/data";

const BLOCK_GROUP_LIMIT = 20;

interface ComparisonChartProps {
  counties: CountyData[];
  metric: MetricConfig;
  selectedFips: string | null;
  onSelect: (fips: string) => void;
  granularity: Granularity;
}

export function ComparisonChart({
  counties,
  metric,
  selectedFips,
  onSelect,
  granularity,
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
  const displayed = isBlockGroup
    ? [
        ...sorted.slice(0, BLOCK_GROUP_LIMIT),
        ...sorted.slice(-BLOCK_GROUP_LIMIT),
      ].filter((v, i, arr) => arr.findIndex((c) => c.county_fips === v.county_fips) === i)
    : sorted;

  const maxVal = Math.max(...sorted.map((c) => (c[metric.key] as number) ?? 0));

  const [r, g, b] = metric.colorScale[metric.colorScale.length - 1];

  const heading =
    granularity === "block_group"
      ? `${metric.label} — Top/Bottom ${BLOCK_GROUP_LIMIT} Block Groups`
      : `${metric.label} — All Counties`;

  return (
    <div className="p-3">
      <h3 className="mb-2 text-xs font-semibold tracking-wider text-slate-600 uppercase dark:text-slate-500">
        {heading}
      </h3>
      <div className="flex flex-col gap-1">
        {displayed.map((county) => {
          const val = (county[metric.key] as number) ?? 0;
          const pct = maxVal > 0 ? (val / maxVal) * 100 : 0;
          const isSelected = county.county_fips === selectedFips;
          const barOpacity = isSelected ? 1 : 0.6;
          const nameShort = isBlockGroup
            ? county.county_fips
            : county.county_name.replace(" County, Texas", "");

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
                className={`${isBlockGroup ? "w-28" : "w-24"} shrink-0 text-right text-xs ${
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
                    backgroundColor: `rgba(${r}, ${g}, ${b}, ${barOpacity})`,
                  }}
                />
              </div>
              <span className="w-18 shrink-0 text-right font-mono text-xs text-slate-700 dark:text-slate-400">
                {formatValue(val, metric.format)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
