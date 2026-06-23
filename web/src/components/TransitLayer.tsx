"use client";

import { useEffect, useMemo, useState } from "react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { BASE_PATH } from "@/lib/data";
import { METROS } from "@/lib/metro";

type TransitMode = "rail" | "bus";

const RAIL_TYPES = new Set(["rail", "tram", "other"]);

export function useTransitLayers(modes: Set<TransitMode>) {
  const [routeData, setRouteData] =
    useState<GeoJSON.FeatureCollection | null>(null);
  const [stopData, setStopData] =
    useState<GeoJSON.FeatureCollection | null>(null);

  const enabled = modes.size > 0;

  useEffect(() => {
    if (!enabled || (routeData && stopData)) return;
    const metroIds = Object.keys(METROS);

    async function fetchAllGeoJSON(filename: string): Promise<GeoJSON.FeatureCollection> {
      const results = await Promise.allSettled(
        metroIds.map((id) =>
          fetch(`${BASE_PATH}/data/${id}/${filename}`).then((r) => {
            if (!r.ok) throw new Error(r.statusText);
            return r.json();
          })
        )
      );
      const features = results
        .filter((r): r is PromiseFulfilledResult<GeoJSON.FeatureCollection> => r.status === "fulfilled")
        .flatMap((r) => r.value.features);
      return { type: "FeatureCollection", features };
    }

    fetchAllGeoJSON("transit_routes.geojson").then(setRouteData);
    fetchAllGeoJSON("transit_stops.geojson").then(setStopData);
  }, [enabled, routeData, stopData]);

  const filteredRoutes = useMemo(() => {
    if (!routeData || !enabled) return null;
    return {
      ...routeData,
      features: routeData.features.filter((f) => {
        const type = f.properties?.route_type as string | undefined;
        const isRail = RAIL_TYPES.has(type ?? "");
        return isRail ? modes.has("rail") : modes.has("bus");
      }),
    };
  }, [routeData, enabled, modes]);

  const filteredStops = useMemo(() => {
    if (!stopData || !enabled) return null;
    return {
      ...stopData,
      features: stopData.features.filter((f) => {
        const stopModes = (f.properties?.modes as string[]) ?? [];
        return stopModes.some((m) => modes.has(m as TransitMode));
      }),
    };
  }, [stopData, enabled, modes]);

  const layers = useMemo(() => {
    if (!enabled) return [];
    const result = [];

    if (filteredRoutes && filteredRoutes.features.length > 0) {
      // Outline layer (wider black line behind the colored line)
      result.push(
        new GeoJsonLayer({
          id: "transit-routes-outline",
          data: filteredRoutes,
          stroked: true,
          filled: false,
          pickable: false,
          getLineColor: [0, 0, 0, 180],
          // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl feature
          getLineWidth: (f: any) => {
            const isRail = RAIL_TYPES.has(f.properties?.route_type ?? "");
            return isRail ? 5.5 : 3;
          },
          lineWidthUnits: "pixels",
          lineCapRounded: true,
          lineJointRounded: true,
          updateTriggers: { getLineWidth: [] },
        }),
      );
      // Colored line on top
      result.push(
        new GeoJsonLayer({
          id: "transit-routes",
          data: filteredRoutes,
          stroked: true,
          filled: false,
          pickable: true,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl feature
          getLineColor: (f: any) => {
            const hex = (f.properties?.color as string) || "";
            if (hex) return hexToRgba(hex, 240);
            const type = f.properties?.route_type as string;
            return RAIL_TYPES.has(type)
              ? ([100, 160, 255, 220] as [number, number, number, number])
              : ([150, 150, 150, 180] as [number, number, number, number]);
          },
          // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl feature
          getLineWidth: (f: any) => {
            const isRail = RAIL_TYPES.has(f.properties?.route_type ?? "");
            return isRail ? 4 : 2;
          },
          lineWidthUnits: "pixels",
          lineCapRounded: true,
          lineJointRounded: true,
          updateTriggers: {
            getLineColor: [],
            getLineWidth: [],
          },
        }),
      );
    }

    if (filteredStops && filteredStops.features.length > 0) {
      result.push(
        new GeoJsonLayer({
          id: "transit-stops",
          data: filteredStops,
          filled: true,
          stroked: true,
          pickable: true,
          pointType: "circle",
          getPointRadius: 120,
          pointRadiusUnits: "meters",
          pointRadiusMinPixels: 2,
          pointRadiusMaxPixels: 6,
          getFillColor: [255, 255, 255, 200],
          getLineColor: [80, 80, 80, 160],
          getLineWidth: 1,
          lineWidthUnits: "pixels",
        }),
      );
    }

    return result;
  }, [enabled, filteredRoutes, filteredStops]);

  return layers;
}

function hexToRgba(
  hex: string,
  alpha: number,
): [number, number, number, number] {
  const cleaned = hex.replace("#", "");
  const r = parseInt(cleaned.substring(0, 2), 16);
  const g = parseInt(cleaned.substring(2, 4), 16);
  const b = parseInt(cleaned.substring(4, 6), 16);
  return [r, g, b, alpha];
}

interface TransitToggleProps {
  railEnabled: boolean;
  busEnabled: boolean;
  onToggleRail: () => void;
  onToggleBus: () => void;
}

export function TransitToggles({
  railEnabled,
  busEnabled,
  onToggleRail,
  onToggleBus,
}: TransitToggleProps) {
  return (
    <>
      <button
        onClick={onToggleRail}
        title={railEnabled ? "Hide rail" : "Show rail"}
        aria-label={railEnabled ? "Hide rail lines" : "Show rail lines"}
        className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
          railEnabled
            ? "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300"
            : "bg-white/80 text-slate-600 hover:bg-slate-100 dark:bg-slate-800/80 dark:text-slate-300 dark:hover:bg-slate-700"
        }`}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="4" y="3" width="16" height="16" rx="2" />
          <path d="M4 11h16" />
          <path d="M12 3v8" />
          <path d="M8 19l-2 3" />
          <path d="M18 22l-2-3" />
          <circle cx="9" cy="15" r="1" />
          <circle cx="15" cy="15" r="1" />
        </svg>
        Rail
      </button>
      <button
        onClick={onToggleBus}
        title={busEnabled ? "Hide bus" : "Show bus"}
        aria-label={busEnabled ? "Hide bus routes" : "Show bus routes"}
        className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
          busEnabled
            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300"
            : "bg-white/80 text-slate-600 hover:bg-slate-100 dark:bg-slate-800/80 dark:text-slate-300 dark:hover:bg-slate-700"
        }`}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M8 6v6" />
          <path d="M16 6v6" />
          <path d="M2 12h20" />
          <path d="M4 6h16a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V8a2 2 0 012-2z" />
          <circle cx="7" cy="18" r="2" />
          <circle cx="17" cy="18" r="2" />
        </svg>
        Bus
      </button>
    </>
  );
}
