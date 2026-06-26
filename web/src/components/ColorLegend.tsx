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
  const cellSize = 22;
  const gap = 2;
  const gridSide = cellSize * 3 + gap * 2;
  const diag = Math.round(gridSide * Math.SQRT2);

  return (
    <div className="flex flex-col items-center">
      {/* Diamond grid — rotated 45° so (min,min) is bottom, (max,max) is top */}
      <div style={{ width: diag, height: diag, position: "relative" }}>
        <div
          data-testid="bivariate-grid"
          className="grid"
          style={{
            gridTemplateColumns: `repeat(3, ${cellSize}px)`,
            gridTemplateRows: `repeat(3, ${cellSize}px)`,
            gap: `${gap}px`,
            position: "absolute",
            left: "50%",
            top: "50%",
            transform: "translate(-50%, -50%) rotate(45deg)",
          }}
        >
          {/* Render rows top-to-bottom = high primary → low primary */}
          {[2, 1, 0].map((ri) =>
            [0, 1, 2].map((ci) => {
              const color = palette[ri][ci];
              const isSelected = selectedCell?.row === ri && selectedCell?.col === ci;
              const dimmed = hasSelection && !isSelected;
              return (
                <button
                  key={`${ri}-${ci}`}
                  type="button"
                  className="rounded-sm border-0 p-0"
                  style={{
                    width: cellSize,
                    height: cellSize,
                    backgroundColor: `rgb(${color[0]},${color[1]},${color[2]})`,
                    opacity: dimmed ? 0.4 : 1,
                    outline: isSelected ? "2px solid white" : "none",
                    outlineOffset: isSelected ? "-2px" : undefined,
                    cursor: "pointer",
                  }}
                  aria-label={`${primaryMetric.label} ${["Low", "Mid", "High"][ri]}, ${secondaryMetric.label} ${["Low", "Mid", "High"][ci]}`}
                  aria-pressed={isSelected}
                  onClick={() => onCellClick(isSelected ? null : { row: ri, col: ci })}
                />
              );
            }),
          )}
        </div>
        {/* Arrows at left and right diamond vertices */}
        <span
          className="absolute text-[11px] text-slate-400 dark:text-slate-500"
          style={{ left: -10, top: diag / 2 - 7 }}
          aria-hidden="true"
        >←</span>
        <span
          className="absolute text-[11px] text-slate-400 dark:text-slate-500"
          style={{ right: -10, top: diag / 2 - 7 }}
          aria-hidden="true"
        >→</span>
      </div>
      {/* Axis labels — along bottom edges, wrapping allowed */}
      <div style={{ width: diag, position: "relative", height: 30, marginTop: 2 }}>
        <span
          className="absolute text-[8px] leading-tight text-slate-400 dark:text-slate-500"
          style={{
            right: "52%",
            bottom: 0,
            transform: "rotate(45deg)",
            transformOrigin: "bottom right",
            maxWidth: diag * 0.55,
            textAlign: "right",
          }}
        >
          {primaryMetric.label}
        </span>
        <span
          className="absolute text-[8px] leading-tight text-slate-400 dark:text-slate-500"
          style={{
            left: "52%",
            bottom: 0,
            transform: "rotate(-45deg)",
            transformOrigin: "bottom left",
            maxWidth: diag * 0.55,
          }}
        >
          {secondaryMetric.label}
        </span>
      </div>
    </div>
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
