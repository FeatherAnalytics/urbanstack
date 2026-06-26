"use client";

import { formatValue, type MetricConfig } from "@/lib/data";

interface ClassifiedLegendProps {
  metric: MetricConfig;
  palette: [number, number, number, number][];
  breaks: number[];
  selectedBins: Set<number>;
  onSelectionChange: (newSelection: Set<number>) => void;
}

function rangeLabel(index: number, breaks: number[], format: MetricConfig["format"]): string {
  if (index === 0) return "N/A";
  const binIdx = index - 1; // palette index → break index
  const lo = binIdx === 0 ? null : breaks[binIdx - 1];
  const hi = binIdx < breaks.length ? breaks[binIdx] : null;
  if (lo === null && hi !== null) return `≤${formatValue(hi, format)}`;
  if (lo !== null && hi === null) return `>${formatValue(lo, format)}`;
  if (lo !== null && hi !== null) return `${formatValue(lo, format)}–${formatValue(hi, format)}`;
  return "";
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

  return (
    <>
      <div className="mb-1 text-[11px] text-slate-600 dark:text-slate-400">{metric.label}</div>
      <div className="flex items-end gap-0.5">
        {binIndices.map((binIdx, paletteIdx) => {
          const [r, g, b] = palette[paletteIdx];
          const isSelected = selectedBins.has(binIdx);
          const hasSelection = selectedBins.size > 0;
          return (
            <button
              key={binIdx}
              aria-label={rangeLabel(paletteIdx, breaks, metric.format)}
              onClick={() => handleClick(binIdx)}
              className="flex flex-col items-center gap-0.5"
            >
              <div
                className={`h-4 w-5 rounded-sm transition-opacity ${
                  isSelected ? "ring-2 ring-white" : ""
                } ${hasSelection && !isSelected ? "opacity-40" : ""}`}
                style={{ backgroundColor: `rgb(${r},${g},${b})` }}
              />
              <span className="text-[8px] leading-tight text-slate-500 dark:text-slate-500">
                {rangeLabel(paletteIdx, breaks, metric.format)}
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
