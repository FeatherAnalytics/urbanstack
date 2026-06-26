"use client";

import { formatValue, PERCENTILE_LABELS, type MetricConfig } from "@/lib/data";

interface ClassifiedLegendProps {
  metric: MetricConfig;
  palette: [number, number, number, number][];
  breaks: number[];
  selectedBins: Set<number>;
  onSelectionChange: (newSelection: Set<number>) => void;
}

function selectedRangeLabel(
  selectedBins: Set<number>,
  breaks: number[],
  format: MetricConfig["format"],
): string | null {
  if (selectedBins.size === 0) return null;
  // Only consider data bins (not N/A which is -1)
  const dataBins = [...selectedBins].filter((b) => b > 0).sort((a, b) => a - b);
  if (dataBins.length === 0) return null;

  const loIdx = dataBins[0] - 1; // break index for lower bound
  const hiIdx = dataBins[dataBins.length - 1] - 1;
  const lo = loIdx === 0 ? null : breaks[loIdx - 1];
  const hi = hiIdx < breaks.length ? breaks[hiIdx] : null;

  const loStr = lo !== null ? formatValue(lo, format) : null;
  const hiStr = hi !== null ? formatValue(hi, format) : null;

  if (loStr && hiStr) return `${loStr}–${hiStr}`;
  if (loStr) return `>${loStr}`;
  if (hiStr) return `≤${hiStr}`;
  return null;
}

export function ClassifiedLegend({
  metric,
  palette,
  breaks,
  selectedBins,
  onSelectionChange,
}: ClassifiedLegendProps) {
  const handleClick = (binIndex: number) => {
    const next = new Set(selectedBins);
    if (next.has(binIndex)) next.delete(binIndex);
    else next.add(binIndex);
    onSelectionChange(next);
  };

  const handleClear = () => onSelectionChange(new Set());

  // Map palette indices to bin indices: palette[0] → binIndex -1, palette[1] → 1, etc.
  const binIndices = [-1, ...Array.from({ length: palette.length - 1 }, (_, i) => i + 1)];

  const rangeStr = selectedRangeLabel(selectedBins, breaks, metric.format);
  const headerLabel = rangeStr ? `${metric.label}: ${rangeStr}` : metric.label;

  return (
    <>
      <div className="mb-1 text-[11px] text-slate-600 dark:text-slate-400">{headerLabel}</div>
      <div className="flex items-end gap-px">
        {binIndices.map((binIdx, paletteIdx) => {
          const [r, g, b] = palette[paletteIdx];
          const isSelected = selectedBins.has(binIdx);
          const hasSelection = selectedBins.size > 0;
          const label = PERCENTILE_LABELS[paletteIdx] ?? "";
          return (
            <button
              key={binIdx}
              aria-label={label}
              onClick={() => handleClick(binIdx)}
              className="flex w-10 flex-col items-center gap-0.5"
            >
              <div
                className={`h-3.5 w-full rounded-sm transition-opacity ${
                  isSelected ? "ring-2 ring-white" : ""
                } ${hasSelection && !isSelected ? "opacity-40" : ""}`}
                style={{ backgroundColor: `rgb(${r},${g},${b})` }}
              />
              <span className="text-[8px] leading-tight text-slate-500 dark:text-slate-500">
                {label}
              </span>
            </button>
          );
        })}
      </div>
      {selectedBins.size > 0 && (
        <button
          onClick={handleClear}
          aria-label="Clear bin selection"
          className="mt-1 text-[10px] text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
        >
          Clear
        </button>
      )}
    </>
  );
}
