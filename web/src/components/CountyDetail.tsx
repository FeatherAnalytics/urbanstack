"use client";

import {
  CATEGORIES,
  formatValue,
  formatRank,
  groupMetricsByCategory,
  type CountyData,
  type MetricConfig,
} from "@/lib/data";

function CloseIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

interface CountyDetailPopupProps {
  county: CountyData | null;
  allCounties: CountyData[];
  selectedMetric: MetricConfig;
  onClose: () => void;
}

export function CountyDetailPopup({
  county,
  allCounties,
  selectedMetric,
  onClose,
}: CountyDetailPopupProps) {
  if (!county) return null;

  return (
    <>
      {/* Desktop: top-right floating card */}
      <div className="popup-enter pointer-events-auto absolute top-3 right-3 z-40 hidden w-72 max-h-[calc(100%-24px)] overflow-y-auto rounded-lg border border-slate-200 bg-white/90 shadow-lg backdrop-blur-md dark:border-slate-600 dark:bg-slate-800/90 lg:block">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white/80 px-3 py-2 backdrop-blur-sm dark:border-slate-600 dark:bg-slate-800/80">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
            {county.county_name}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close county detail"
            className="rounded p-0.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-300"
          >
            <CloseIcon />
          </button>
        </div>
        <MetricList
          county={county}
          allCounties={allCounties}
          selectedMetric={selectedMetric}
        />
      </div>

      {/* Mobile: bottom sheet */}
      <div className="sheet-enter pointer-events-auto absolute inset-x-0 bottom-0 z-40 max-h-[60%] overflow-y-auto rounded-t-xl border-t border-slate-200 bg-white/95 shadow-2xl backdrop-blur-md dark:border-slate-600 dark:bg-slate-800/95 lg:hidden">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white/80 px-3 py-2 backdrop-blur-sm dark:border-slate-600 dark:bg-slate-800/80">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
            {county.county_name}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close county detail"
            className="rounded p-0.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-300"
          >
            <CloseIcon />
          </button>
        </div>
        <MetricList
          county={county}
          allCounties={allCounties}
          selectedMetric={selectedMetric}
        />
      </div>
    </>
  );
}

/** Shared metric list used by both desktop popup and mobile bottom sheet */
function MetricList({
  county,
  allCounties,
  selectedMetric,
}: {
  county: CountyData;
  allCounties: CountyData[];
  selectedMetric: MetricConfig;
}) {
  const metricsByCategory = groupMetricsByCategory();

  return (
    <div className="flex flex-col gap-3 p-3">
      {CATEGORIES.map((category) => {
        const filteredMetrics = metricsByCategory[category].filter((m) => {
          const val = county[m.key];
          return val !== null && val !== undefined && !Number.isNaN(val as number);
        });
        if (filteredMetrics.length === 0) return null;
        return (
          <div key={category} className="[&:not(:first-child)]:border-t [&:not(:first-child)]:border-slate-100 [&:not(:first-child)]:pt-2 [&:not(:first-child)]:mt-1 dark:[&:not(:first-child)]:border-slate-700">
            <h3 className="mb-1 text-[11px] font-semibold tracking-wider text-slate-400 uppercase dark:text-slate-500">
              {category}
            </h3>
            <div className="flex flex-col gap-px">
              {filteredMetrics.map((metric) => {
                const val = county[metric.key] as number | null;
                const rankLabel = formatRank(county, metric.key, allCounties);
                const isSelected = metric.key === selectedMetric.key;

                // Position in distribution: 0 (lowest) to 1 (highest)
                const allVals = allCounties
                  .map(c => c[metric.key] as number | null)
                  .filter((v): v is number => v !== null && Number.isFinite(v));
                allVals.sort((a, b) => a - b);
                const rank = val !== null ? allVals.findIndex(v => v >= val) : -1;
                const pctPosition = allVals.length > 1 && rank >= 0 ? (rank / (allVals.length - 1)) * 100 : 50;

                return (
                  <div
                    key={metric.key}
                    className={`relative overflow-hidden rounded px-2 py-0.5 text-sm transition-colors ${
                      isSelected
                        ? "bg-blue-50 ring-1 ring-blue-200 dark:bg-blue-900/20 dark:ring-blue-800"
                        : ""
                    }`}
                  >
                    {/* Distribution position track */}
                    {val !== null && (
                      <div className="absolute inset-x-2 bottom-0 h-[2px]">
                        <div className="h-full w-full rounded-full bg-slate-200/40 dark:bg-slate-600/30" />
                        <div
                          className="absolute top-[-1px] h-[4px] w-[4px] rounded-full bg-slate-400 dark:bg-slate-400"
                          style={{ left: `${pctPosition}%`, transform: "translateX(-50%)" }}
                        />
                      </div>
                    )}
                    <div className="flex items-baseline justify-between">
                      <span className={isSelected
                        ? "font-medium text-slate-900 dark:text-white"
                        : "text-slate-500 dark:text-slate-400"
                      }>
                        {metric.label}
                      </span>
                      <span className="flex items-baseline gap-2">
                        <span className="font-mono text-slate-900 dark:text-white">
                          {formatValue(val, metric.format)}
                        </span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">
                          {rankLabel}
                        </span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
