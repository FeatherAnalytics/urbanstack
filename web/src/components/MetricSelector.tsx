"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  CATEGORIES,
  METRIC_COMBOS,
  METRICS,
  groupMetricsByCategory,
  type CountyData,
  type MetricCombo,
  type MetricConfig,
} from "@/lib/data";

interface MetricSelectorProps {
  selected: MetricConfig;
  onSelect: (metric: MetricConfig) => void;
  counties: CountyData[];
  secondaryMetric: MetricConfig | null;
  onSelectSecondary: (metric: MetricConfig | null) => void;
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

function MetricList({
  grouped,
  visibleCategories,
  selected,
  onSelect,
  counties,
  exclude,
  navRef,
}: {
  grouped: Record<string, MetricConfig[]>;
  visibleCategories: string[];
  selected: MetricConfig | null;
  onSelect: (m: MetricConfig) => void;
  counties: CountyData[];
  exclude: string | null;
  navRef: React.RefObject<HTMLElement | null>;
}) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

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
    [navRef],
  );

  return (
    <>
      {visibleCategories.map((category) => {
        const metrics = grouped[category].filter(
          (m) => hasData(counties, m.key) && m.key !== exclude,
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
                  onMouseLeave={() => setTooltip(null)}
                  className={`flex w-full items-baseline justify-between rounded px-2 py-1 text-left text-sm transition-colors ${
                    selected?.key === metric.key
                      ? "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white"
                      : "text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  <span>{metric.label}</span>
                  {metric.dateRange && (
                    <span className="ml-1 text-[10px] text-slate-400 dark:text-slate-600">
                      {metric.dateRange}
                    </span>
                  )}
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
          <p className="text-slate-700 dark:text-slate-300">{tooltip.metric.description}</p>
          <p className="mt-1 text-slate-400 dark:text-slate-500">
            Source: {tooltip.metric.source}
            {tooltip.metric.dateRange && ` · ${tooltip.metric.dateRange}`}
          </p>
        </div>
      )}
    </>
  );
}

export function MetricSelector({
  selected,
  onSelect,
  counties,
  secondaryMetric,
  onSelectSecondary,
}: MetricSelectorProps) {
  const grouped = useMemo(() => groupMetricsByCategory(), []);
  const navRef = useRef<HTMLElement>(null);
  const [compareOpen, setCompareOpen] = useState(false);

  const visibleCategories = useMemo(() => {
    return CATEGORIES.filter((cat) =>
      grouped[cat].some((m) => hasData(counties, m.key)),
    );
  }, [counties, grouped]);

  const handleComboClick = useCallback(
    (combo: MetricCombo) => {
      const primary = METRICS.find((m) => m.key === combo.primary);
      const secondary = METRICS.find((m) => m.key === combo.secondary);
      if (primary && secondary) {
        onSelect(primary);
        onSelectSecondary(secondary);
        setCompareOpen(true);
      }
    },
    [onSelect, onSelectSecondary],
  );

  const handleClearSecondary = useCallback(() => {
    onSelectSecondary(null);
    setCompareOpen(false);
  }, [onSelectSecondary]);

  const availableCombos = useMemo(() => {
    return METRIC_COMBOS.filter(
      (c) => hasData(counties, c.primary) && hasData(counties, c.secondary),
    );
  }, [counties]);

  return (
    <nav ref={navRef} className="relative flex flex-col gap-3 p-3">
      <div className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-500">
        {compareOpen ? "Primary" : "Metric"}
      </div>
      <MetricList
        grouped={grouped}
        visibleCategories={visibleCategories}
        selected={selected}
        onSelect={onSelect}
        counties={counties}
        exclude={secondaryMetric?.key ?? null}
        navRef={navRef}
      />

      {compareOpen && secondaryMetric !== null && (
        <>
          <div className="flex items-center justify-between border-t border-slate-200 pt-2 dark:border-slate-700">
            <span className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-500">
              Secondary
            </span>
            <button
              onClick={handleClearSecondary}
              className="text-[10px] text-slate-400 hover:text-red-500 dark:text-slate-500"
            >
              ✕ clear
            </button>
          </div>
          <MetricList
            grouped={grouped}
            visibleCategories={visibleCategories}
            selected={secondaryMetric}
            onSelect={onSelectSecondary}
            counties={counties}
            exclude={selected.key}
            navRef={navRef}
          />
        </>
      )}

      {!compareOpen && (
        <button
          onClick={() => setCompareOpen(true)}
          className="mt-1 border-t border-slate-200 pt-2 text-left text-xs text-slate-400 hover:text-slate-600 dark:border-slate-700 dark:text-slate-500 dark:hover:text-slate-300"
        >
          + Compare metric...
        </button>
      )}

      {compareOpen && secondaryMetric === null && (
        <div className="border-t border-slate-200 pt-2 dark:border-slate-700">
          <span className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-500">
            Secondary
          </span>
          <p className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
            Select a metric above, or pick a combo:
          </p>
        </div>
      )}

      {compareOpen && availableCombos.length > 0 && (
        <div className="border-t border-slate-200 pt-2 dark:border-slate-700">
          <div className="mb-1 text-[10px] text-slate-400 dark:text-slate-500">Quick combos</div>
          <div className="flex flex-col gap-1">
            {availableCombos.map((combo) => (
              <button
                key={combo.key}
                onClick={() => handleComboClick(combo)}
                className="rounded border border-purple-300/30 bg-purple-50/50 px-2 py-1 text-left text-[11px] text-purple-700 hover:bg-purple-100/50 dark:border-purple-600/30 dark:bg-purple-900/20 dark:text-purple-300 dark:hover:bg-purple-800/30"
                title={combo.description}
              >
                ⚡ {combo.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
