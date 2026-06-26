"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
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
  left: number;
  width: number;
  above: boolean;
}

function computeTooltipPosition(
  btn: HTMLElement,
  nav: HTMLElement,
): { top: number; left: number; width: number; above: boolean } {
  const navRect = nav.getBoundingClientRect();
  const btnRect = btn.getBoundingClientRect();
  const top = Math.max(btnRect.top, 0);
  return { top, left: navRect.right + 8, width: 240, above: false };
}

function TooltipPopup({ state }: { state: TooltipState | null }) {
  if (!state) return null;
  return createPortal(
    <div
      className="pointer-events-none fixed z-[9999] rounded border border-slate-200 bg-white p-2 text-xs shadow-lg dark:border-slate-600 dark:bg-slate-800"
      style={{ top: state.top, left: state.left, width: state.width }}
    >
      <p className="text-slate-700 dark:text-slate-300">{state.metric.description}</p>
      <p className="mt-1 text-slate-400 dark:text-slate-500">
        Source: {state.metric.source}
        {state.metric.dateRange && ` · ${state.metric.dateRange}`}
      </p>
    </div>,
    document.body,
  );
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
      const pos = computeTooltipPosition(btn, nav);
      setTooltip({ metric, ...pos });
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
                    <span className="ml-1 text-[10px] text-slate-400 dark:text-slate-500">
                      {metric.dateRange}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        );
      })}
      <TooltipPopup state={tooltip} />
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
  const [comboTooltip, setComboTooltip] = useState<TooltipState | null>(null);

  const activeComboKey = useMemo(
    () => METRIC_COMBOS.find(
      (c) => c.primary === selected.key && c.secondary === secondaryMetric?.key,
    )?.key ?? null,
    [selected.key, secondaryMetric?.key],
  );

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
      }
    },
    [onSelect, onSelectSecondary],
  );

  const availableCombos = useMemo(() => {
    return METRIC_COMBOS.filter(
      (c) => hasData(counties, c.primary) && hasData(counties, c.secondary),
    );
  }, [counties]);

  return (
    <nav ref={navRef} className="relative flex flex-col gap-3 p-3">
      <div className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-500">
        Metric
      </div>

      {/* Derived metrics — elevated position for discoverability */}
      {availableCombos.length > 0 && (
        <div className="rounded-md bg-slate-50 p-2 dark:bg-slate-800/50">
          <h3 className="mb-1 text-[11px] font-semibold tracking-wider text-slate-600 uppercase dark:text-slate-500">
            Derived
          </h3>
          <div className="flex flex-col gap-0.5">
            {availableCombos.map((combo) => (
              <button
                key={combo.key}
                onClick={() => handleComboClick(combo)}
                onMouseEnter={(e) => {
                  const primary = METRICS.find((m) => m.key === combo.primary);
                  if (!primary) return;
                  const nav = navRef.current;
                  if (!nav) return;
                  const pos = computeTooltipPosition(e.currentTarget, nav);
                  setComboTooltip({ metric: { ...primary, description: combo.description, source: "Pre-built combination" }, ...pos });
                }}
                onMouseLeave={() => setComboTooltip(null)}
                className={`flex w-full items-baseline rounded px-2 py-1 text-left text-sm transition-colors ${
                  activeComboKey === combo.key
                    ? "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white"
                    : "text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                }`}
              >
                {combo.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Individual metrics by category */}
      <MetricList
        grouped={grouped}
        visibleCategories={visibleCategories}
        selected={activeComboKey ? null : selected}
        onSelect={onSelect}
        counties={counties}
        exclude={secondaryMetric?.key ?? null}
        navRef={navRef}
      />

      <TooltipPopup state={comboTooltip} />
    </nav>
  );
}
