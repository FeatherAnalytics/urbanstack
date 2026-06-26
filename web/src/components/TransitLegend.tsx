"use client";

import { useMemo, useState } from "react";
import { RAIL_TYPES, getTransitRouteList, type TransitRouteInfo } from "./TransitLayer";

function defaultColor(type: string): string {
  return RAIL_TYPES.has(type) ? "#64A0FF" : "#969696";
}

interface TransitLegendProps {
  routes: GeoJSON.FeatureCollection | null;
}

export function TransitLegend({ routes }: TransitLegendProps) {
  const [collapsed, setCollapsed] = useState(false);
  const routeList = useMemo(() => getTransitRouteList(routes), [routes]);
  const byAgency = useMemo(() => {
    const grouped: Record<string, TransitRouteInfo[]> = {};
    for (const r of routeList) {
      (grouped[r.agency] ??= []).push(r);
    }
    return grouped;
  }, [routeList]);

  if (routeList.length === 0) return null;

  return (
    <div className="absolute bottom-14 left-3 z-30 max-h-64 w-56 overflow-y-auto rounded-lg border border-slate-200/80 bg-white/90 shadow-md backdrop-blur-sm dark:border-slate-600/80 dark:bg-slate-800/90">
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="sticky top-0 flex w-full items-center justify-between bg-white/95 px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 dark:bg-slate-800/95 dark:text-slate-200"
      >
        Transit Routes ({routeList.length})
        <span className="text-[10px] text-slate-400">{collapsed ? "+" : "-"}</span>
      </button>
      {!collapsed && (
        <div className="px-2.5 pb-2">
          {Object.entries(byAgency).map(([agency, agencyRoutes]) => (
            <div key={agency} className="mt-1.5 first:mt-0">
              <div className="text-[10px] font-medium text-slate-500 dark:text-slate-400">
                {agency}
              </div>
              <div className="mt-0.5 space-y-px">
                {agencyRoutes.map((r, i) => (
                  <div
                    key={`${r.agency}-${r.name}-${r.type}-${r.color}-${i}`}
                    className="flex items-center gap-1.5 text-[10px] text-slate-600 dark:text-slate-300"
                  >
                    <span
                      className="inline-block h-2 w-4 shrink-0 rounded-sm"
                      style={{ backgroundColor: r.color || defaultColor(r.type) }}
                    />
                    <span className="truncate">{r.name || "(unnamed)"}</span>
                    <span className="ml-auto shrink-0 text-[9px] text-slate-400">
                      {RAIL_TYPES.has(r.type) ? "rail" : "bus"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
