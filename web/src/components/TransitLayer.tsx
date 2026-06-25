"use client";

import { useEffect, useMemo, useState } from "react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { BASE_PATH } from "@/lib/data";

type TransitMode = "rail" | "bus";

export const RAIL_TYPES = new Set(["rail", "tram", "other"]);

// yagni: frontend overrides until pipeline normalizes GTFS names at extract time
const AGENCY_OVERRIDES: Record<string, string> = {
  "TRE - TRINITY RAILWAY": "Trinity Metro",
};

const NAME_OVERRIDES: Record<string, string> = {
  "TRE - TRINITY RAILWAY": "Trinity Railway Express",
  "RED - DART LIGHT RAIL - RED LINE": "Red",
};

const EMPTY_FC: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export function useTransitLayers(modes: Set<TransitMode>, selectedMetro: string | null) {
  const [routeData, setRouteData] =
    useState<GeoJSON.FeatureCollection | null>(null);
  const [stopData, setStopData] =
    useState<GeoJSON.FeatureCollection | null>(null);

  const enabled = modes.size > 0 && selectedMetro !== null;

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resetting state when selectedMetro changes
    setRouteData(null);
    setStopData(null);
    if (!selectedMetro) return;

    const metro = selectedMetro;
    function fetchGeoJSON(filename: string): Promise<GeoJSON.FeatureCollection> {
      return fetch(`${BASE_PATH}/data/${metro}/${filename}`).then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      });
    }

    fetchGeoJSON("transit_routes.geojson")
      .then(setRouteData)
      .catch((err) => { console.error("Failed to load transit routes:", err); setRouteData(EMPTY_FC); });
    fetchGeoJSON("transit_stops.geojson")
      .then(setStopData)
      .catch((err) => { console.error("Failed to load transit stops:", err); setStopData(EMPTY_FC); });
  }, [selectedMetro]);

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

  const availableModes = useMemo(() => {
    if (!routeData) return { rail: false, bus: false };
    let hasRail = false;
    let hasBus = false;
    for (const f of routeData.features) {
      const type = f.properties?.route_type as string | undefined;
      if (RAIL_TYPES.has(type ?? "")) hasRail = true;
      else hasBus = true;
      if (hasRail && hasBus) break;
    }
    return { rail: hasRail, bus: hasBus };
  }, [routeData]);

  return { layers, routes: filteredRoutes, availableModes };
}

export interface TransitRouteInfo {
  agency: string;
  name: string;
  type: string;
  color: string;
}

function normalizeName(raw: string): string {
  const idx = raw.indexOf(" - ");
  const short = idx >= 0 ? raw.slice(0, idx).trim() : raw.trim();
  const long = idx >= 0 ? raw.slice(idx + 3).trim() : "";

  if (/^\d+[A-Z]?X?$/.test(short) || /^[A-Z]{1,3}$/.test(short)) {
    if (!long) return short;
    const desc = long
      .replace(/\s*(DART\s+)?LIGHT RAIL\b/gi, "")
      .replace(/\s*LINE\b/gi, "")
      .replace(/\s*RAILWAY\b/gi, "")
      .replace(/^\s*-\s*/, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!desc || desc.toLowerCase() === short.toLowerCase()) return short;
    return `${short} ${toTitle(desc)}`;
  }

  const cleaned = short
    .replace(/\s*(LIGHT RAIL|RAILWAY)\b/gi, "")
    .replace(/\s*LINE\b$/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  return toTitle(cleaned || short);
}

function toTitle(s: string): string {
  return s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

export function getTransitRouteList(
  routes: GeoJSON.FeatureCollection | null,
): TransitRouteInfo[] {
  if (!routes || routes.features.length === 0) return [];
  const seen = new Set<string>();
  const list: TransitRouteInfo[] = [];
  for (const f of routes.features) {
    const p = f.properties ?? {};
    const key = `${p.agency}::${p.route_name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const rawName = p.route_name ?? "";
    const agency = AGENCY_OVERRIDES[rawName] ?? p.agency ?? "";
    list.push({
      agency,
      name: NAME_OVERRIDES[rawName] ?? normalizeName(rawName),
      type: p.route_type ?? "bus",
      color: p.color ?? "",
    });
  }
  list.sort((a, b) => a.agency.localeCompare(b.agency) || a.name.localeCompare(b.name));
  return list;
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
  railAvailable?: boolean;
  busAvailable?: boolean;
}

export function TransitToggles({
  railEnabled,
  busEnabled,
  onToggleRail,
  onToggleBus,
  railAvailable = true,
  busAvailable = true,
}: TransitToggleProps) {
  return (
    <>
      {railAvailable && (
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
      )}
      {busAvailable && (
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
      )}
    </>
  );
}
