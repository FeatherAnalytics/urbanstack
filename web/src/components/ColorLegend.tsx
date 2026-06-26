"use client";

import { BIVARIATE_PALETTE, formatValue, type ColorScaleMode, type Granularity, type MetricConfig } from "@/lib/data";
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
  quantileBreaks?: number[] | null;
  classifiedPalette?: [number, number, number, number][] | null;
  selectedBins?: Set<number>;
  onSelectionChange?: (newSelection: Set<number>) => void;
  bivariatePalette?: [number, number, number][][] | null;
  selectedBivariateCell?: { row: number; col: number } | null;
  onBivariateCellClick?: (cell: { row: number; col: number } | null) => void;
}

function GradientLegend({ metric, minMax }: { metric: MetricConfig; minMax: { min: number; max: number } }) {
  const stops = metric.colorScale;
  const gradientStops = stops.map((s, i) => {
    const pct = (i / (stops.length - 1)) * 100;
    return `rgb(${s[0]},${s[1]},${s[2]}) ${pct}%`;
  });

  return (
    <>
      <div className="mb-1 text-[11px] text-slate-600 dark:text-slate-400">{metric.label}</div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] tabular-nums text-slate-500 dark:text-slate-500">
          {formatValue(minMax.min, metric.format)}
        </span>
        <div
          className="h-3 min-w-16 flex-1 rounded-sm"
          style={{ background: `linear-gradient(to right, ${gradientStops.join(", ")})` }}
          role="img"
          aria-label={`Color scale from ${formatValue(minMax.min, metric.format)} to ${formatValue(minMax.max, metric.format)}`}
        />
        <span className="text-[10px] tabular-nums text-slate-500 dark:text-slate-500">
          {formatValue(minMax.max, metric.format)}
        </span>
      </div>
    </>
  );
}

interface BivariateLegendProps {
  primaryMetric: MetricConfig;
  secondaryMetric: MetricConfig;
  palette: [number, number, number][][];
  selectedCell: { row: number; col: number } | null;
  onCellClick: (cell: { row: number; col: number } | null) => void;
}

function BivariateLegend({
  primaryMetric,
  secondaryMetric,
  palette,
  selectedCell,
  onCellClick,
}: BivariateLegendProps) {
  const hasSelection = selectedCell !== null;

  return (
    <>
      <div className="mb-1.5 text-[11px] text-slate-600 dark:text-slate-400">
        {primaryMetric.label} &times; {secondaryMetric.label}
      </div>
      <div className="flex items-end gap-1">
        <div
          className="text-[9px] text-slate-500 dark:text-slate-500"
          style={{ writingMode: "vertical-lr", transform: "rotate(180deg)", height: 72 }}
        >
          {primaryMetric.label} &rarr;
        </div>
        <div>
          <div
            data-testid="bivariate-grid"
            className="grid gap-px"
            style={{
              gridTemplateColumns: "repeat(3, 22px)",
              gridTemplateRows: "repeat(3, 22px)",
              transform: "scaleY(-1)",
            }}
          >
            {palette.flatMap((row, ri) =>
              row.map((color, ci) => {
                const isSelected = selectedCell?.row === ri && selectedCell?.col === ci;
                const dimmed = hasSelection && !isSelected;
                return (
                  <button
                    key={`${ri}-${ci}`}
                    type="button"
                    className="rounded-sm border-0 p-0"
                    style={{
                      backgroundColor: `rgb(${color[0]},${color[1]},${color[2]})`,
                      opacity: dimmed ? 0.4 : 1,
                      outline: isSelected ? "2px solid white" : "none",
                      outlineOffset: isSelected ? "-2px" : undefined,
                      cursor: "pointer",
                      // scaleY(-1) on parent flips visually; transform back for button semantics
                      transform: "scaleY(-1)",
                    }}
                    title={`Primary: ${["Low", "Mid", "High"][ri]}, Secondary: ${["Low", "Mid", "High"][ci]}`}
                    aria-label={`${primaryMetric.label} ${["Low", "Mid", "High"][ri]}, ${secondaryMetric.label} ${["Low", "Mid", "High"][ci]}`}
                    aria-pressed={isSelected}
                    onClick={() => onCellClick(isSelected ? null : { row: ri, col: ci })}
                  />
                );
              }),
            )}
          </div>
          <div className="mt-0.5 text-center text-[9px] text-slate-500 dark:text-slate-500">
            {secondaryMetric.label} &rarr;
          </div>
        </div>
      </div>
    </>
  );
}

export function ColorLegend({
  primaryMetric,
  secondaryMetric,
  primaryMinMax,
  secondaryMinMax,
  colorScaleMode,
  onToggleMode,
  onExitCompare,
  granularity,
  quantileBreaks = null,
  classifiedPalette = null,
  selectedBins = new Set<number>(),
  onSelectionChange = () => {},
  bivariatePalette = null,
  selectedBivariateCell = null,
  onBivariateCellClick = () => {},
}: ColorLegendProps) {
  const isBivariate = secondaryMetric !== null && secondaryMinMax !== null;
  const isClassified = !isBivariate && quantileBreaks !== null && classifiedPalette !== null;
  const showToggle = granularity !== "metro";

  const effectiveBivariatePalette = bivariatePalette ?? BIVARIATE_PALETTE;

  return (
    <div className="rounded-lg border border-slate-200/80 bg-white/90 p-2.5 shadow-md backdrop-blur-sm dark:border-slate-600/80 dark:bg-slate-800/90">
      {isBivariate ? (
        <BivariateLegend
          primaryMetric={primaryMetric}
          secondaryMetric={secondaryMetric!}
          palette={effectiveBivariatePalette}
          selectedCell={selectedBivariateCell ?? null}
          onCellClick={onBivariateCellClick}
        />
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
}
