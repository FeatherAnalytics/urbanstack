"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  CATEGORIES,
  groupMetricsByCategory,
  type CountyData,
  type MetricConfig,
} from "@/lib/data";

interface MetricSelectorProps {
  selected: MetricConfig;
  onSelect: (metric: MetricConfig) => void;
  counties: CountyData[];
}

function hasData(counties: CountyData[], key: string): boolean {
  return counties.some((c) => {
    const val = c[key as keyof CountyData];
    return val !== null && val !== undefined && val !== 0 && !Number.isNaN(val);
  });
}

interface TooltipState {
  metric: MetricConfig;
  top: number;
  above: boolean;
}

export function MetricSelector({
  selected,
  onSelect,
  counties,
}: MetricSelectorProps) {
  const grouped = groupMetricsByCategory();
  const navRef = useRef<HTMLElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const visibleCategories = useMemo(() => {
    return CATEGORIES.filter((cat) =>
      grouped[cat].some((m) => hasData(counties, m.key)),
    );
  }, [counties, grouped]);

  const handleMouseEnter = useCallback(
    (metric: MetricConfig, e: React.MouseEvent<HTMLButtonElement>) => {
      const btn = e.currentTarget;
      const nav = navRef.current;
      if (!nav) return;

      const navRect = nav.getBoundingClientRect();
      const btnRect = btn.getBoundingClientRect();
      const spaceBelow = navRect.bottom - btnRect.bottom;
      const above = spaceBelow < 80;
      const top = above
        ? btnRect.top - navRect.top + nav.scrollTop - 4
        : btnRect.bottom - navRect.top + nav.scrollTop + 4;

      setTooltip({ metric, top, above });
    },
    [],
  );

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  return (
    <nav ref={navRef} className="relative flex flex-col gap-3 p-3">
      {visibleCategories.map((category) => {
        const metrics = grouped[category].filter((m) =>
          hasData(counties, m.key),
        );
        if (metrics.length === 0) return null;
        return (
          <div key={category}>
            <h3 className="mb-1 text-[11px] font-semibold tracking-wider text-slate-600 uppercase dark:text-slate-500">
              {category}
            </h3>
            <div className="flex flex-col gap-0.5">
              {metrics.map((metric) => (
                <button
                  key={metric.key}
                  onClick={() => onSelect(metric)}
                  onMouseEnter={(e) => handleMouseEnter(metric, e)}
                  onMouseLeave={handleMouseLeave}
                  className={`w-full rounded px-2 py-1 text-left text-sm transition-colors ${
                    selected.key === metric.key
                      ? "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white"
                      : "text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  {metric.label}
                </button>
              ))}
            </div>
          </div>
        );
      })}

      {tooltip && (
        <div
          className={`pointer-events-none absolute left-1 right-1 z-50 rounded border border-slate-200 bg-white p-2 text-xs shadow-lg dark:border-slate-600 dark:bg-slate-800 ${
            tooltip.above ? "-translate-y-full" : ""
          }`}
          style={{ top: tooltip.top }}
        >
          <p className="text-slate-700 dark:text-slate-300">
            {tooltip.metric.description}
          </p>
          <p className="mt-1 text-slate-400 dark:text-slate-500">
            Source: {tooltip.metric.source}
          </p>
        </div>
      )}
    </nav>
  );
}
