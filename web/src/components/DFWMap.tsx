"use client";

import { useCallback, useMemo } from "react";
import { Map as MapGL } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import type { Layer } from "@deck.gl/core";
import {
  interpolateColor,
  formatValue,
  type CountyData,
  type Granularity,
  type MetricConfig,
} from "@/lib/data";
import "maplibre-gl/dist/maplibre-gl.css";

const BASEMAP_DARK =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const BASEMAP_LIGHT =
  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

const INITIAL_VIEW = {
  longitude: -96.85,
  latitude: 32.78,
  zoom: 8,
  pitch: 0,
  bearing: 0,
};

interface DFWMapProps {
  geojson: GeoJSON.FeatureCollection | null;
  counties: CountyData[];
  metric: MetricConfig;
  selectedFips: string | null;
  onSelectCounty: (fips: string | null) => void;
  onHoverCounty: (county: CountyData | null, x: number, y: number) => void;
  isDark: boolean;
  /** Current data granularity — controls fill alpha, line width, and metro matching */
  granularity: Granularity;
  /** Additional deck.gl layers rendered on top of the choropleth */
  overlayLayers?: Layer[];
}

export function DFWMap({
  geojson,
  counties,
  metric,
  selectedFips,
  onSelectCounty,
  onHoverCounty,
  isDark,
  granularity,
  overlayLayers = [],
}: DFWMapProps) {
  const isMetro = granularity === "metro";
  const isBlockGroup = granularity === "block_group";

  // Build a lookup from FIPS -> CountyData
  const dataByFips = useMemo(() => {
    const map = new Map<string, CountyData>();
    for (const c of counties) {
      map.set(c.county_fips, c);
    }
    return map;
  }, [counties]);

  // Compute min/max for normalization, excluding null/NaN
  const [minVal, maxVal] = useMemo(() => {
    const values = counties
      .map((c) => c[metric.key] as number | null)
      .filter((v): v is number => v !== null && v !== undefined && !Number.isNaN(v));
    if (values.length === 0) return [0, 0];
    return [Math.min(...values), Math.max(...values)];
  }, [counties, metric.key]);

  // Fill alpha varies by granularity: block groups need transparency so labels show through
  const fillAlpha = isBlockGroup ? 120 : 200;

  const getFillColor = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl feature type
    (feature: any): [number, number, number, number] => {
      // Metro: single record applies to all features
      if (isMetro && counties.length > 0) {
        const record = counties[0];
        const val = record[metric.key] as number | null;
        if (val === null || val === undefined || Number.isNaN(val)) return [40, 40, 40, 120];
        const t = 0.5; // midpoint — single value, no variation
        const color = interpolateColor(t, metric.colorScale);
        color[3] = fillAlpha;
        return color;
      }

      const fips = feature.properties?.GEOID as string | undefined;
      if (!fips) return [40, 40, 40, 160];
      const county = dataByFips.get(fips);
      if (!county) return [40, 40, 40, 160];

      const val = county[metric.key] as number | null;
      if (val === null || val === undefined || Number.isNaN(val)) return [40, 40, 40, 120];
      const range = maxVal - minVal;
      const t = range > 0 ? (val - minVal) / range : 0.5;
      const color = interpolateColor(t, metric.colorScale);
      color[3] = fillAlpha;
      return color;
    },
    [dataByFips, metric, minVal, maxVal, isMetro, counties, fillAlpha],
  );

  const getLineColor = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl feature type
    (feature: any): [number, number, number, number] => {
      const fips = feature.properties?.GEOID as string | undefined;
      if (fips === selectedFips) {
        return isDark ? [255, 255, 255, 255] : [15, 23, 42, 255];
      }
      // Block groups: more transparent borders to reduce visual noise
      if (isBlockGroup) {
        return isDark ? [80, 80, 80, 80] : [148, 163, 184, 80];
      }
      return isDark ? [100, 100, 100, 180] : [148, 163, 184, 180];
    },
    [selectedFips, isDark, isBlockGroup],
  );

  const getLineWidth = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl feature type
    (feature: any): number => {
      const fips = feature.properties?.GEOID as string | undefined;
      if (fips === selectedFips) return 3;
      return isBlockGroup ? 0.5 : 1;
    },
    [selectedFips, isBlockGroup],
  );

  const layers = useMemo(() => {
    if (!geojson) return [...overlayLayers];

    return [
      new GeoJsonLayer({
        id: "counties",
        data: geojson,
        filled: true,
        stroked: true,
        pickable: true,
        getFillColor,
        getLineColor,
        getLineWidth,
        lineWidthUnits: "pixels",
        updateTriggers: {
          getFillColor: [metric.key, minVal, maxVal, granularity],
          getLineColor: [selectedFips, isDark, granularity],
          getLineWidth: [selectedFips, granularity],
        },
      }),
      ...overlayLayers,
    ];
  }, [
    geojson,
    getFillColor,
    getLineColor,
    getLineWidth,
    metric.key,
    minVal,
    maxVal,
    selectedFips,
    isDark,
    granularity,
    overlayLayers,
  ]);

  const handleClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl event type
    (info: any) => {
      if (info.object) {
        // Metro: clicking any polygon selects the single metro record
        if (isMetro && counties.length > 0) {
          onSelectCounty(counties[0].county_fips);
          return;
        }
        const fips = info.object.properties?.GEOID as string | undefined;
        onSelectCounty(fips ?? null);
      } else {
        onSelectCounty(null);
      }
    },
    [onSelectCounty, isMetro, counties],
  );

  const handleHover = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl event type
    (info: any) => {
      if (info.object) {
        // Metro: hovering any polygon shows the single metro record
        if (isMetro && counties.length > 0) {
          onHoverCounty(counties[0], info.x ?? 0, info.y ?? 0);
          return;
        }
        const fips = info.object.properties?.GEOID as string | undefined;
        const county = fips ? dataByFips.get(fips) ?? null : null;
        onHoverCounty(county, info.x ?? 0, info.y ?? 0);
      } else {
        onHoverCounty(null, 0, 0);
      }
    },
    [dataByFips, onHoverCounty, isMetro, counties],
  );

  const basemapStyle = isDark ? BASEMAP_DARK : BASEMAP_LIGHT;

  return (
    <div className="relative h-full w-full">
      <DeckGL
        initialViewState={INITIAL_VIEW}
        controller={true}
        layers={layers}
        onClick={handleClick}
        onHover={handleHover}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
      >
        <MapGL reuseMaps mapStyle={basemapStyle} />
      </DeckGL>
    </div>
  );
}

interface MapTooltipProps {
  county: CountyData | null;
  metric: MetricConfig;
  x: number;
  y: number;
  containerRef?: React.RefObject<HTMLElement | null>;
}

export function MapTooltip({ county, metric, x, y, containerRef }: MapTooltipProps) {
  if (!county) return null;

  const val = county[metric.key] as number | null;
  const rect = containerRef?.current?.getBoundingClientRect();
  const absX = (rect?.left ?? 0) + x;
  const absY = (rect?.top ?? 0) + y;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const flipLeft = absX > vw - 260;
  const flipUp = absY > vh - 80;

  return (
    <div
      className="pointer-events-none fixed z-[9999] w-max max-w-[240px] rounded border border-slate-200 bg-white/95 px-3 py-2 text-sm shadow-lg dark:border-slate-600 dark:bg-slate-800/95"
      style={{
        left: flipLeft ? absX - 12 : absX + 12,
        top: flipUp ? absY - 12 : absY + 12,
        transform: `${flipLeft ? "translateX(-100%)" : ""} ${flipUp ? "translateY(-100%)" : ""}`.trim() || undefined,
      }}
    >
      <div className="font-semibold text-slate-900 dark:text-white">
        {county.county_name}
      </div>
      <div className="text-slate-500 dark:text-slate-400">
        {metric.label}:{" "}
        <span className="font-mono text-slate-900 dark:text-white">
          {formatValue(val, metric.format)}
        </span>
      </div>
    </div>
  );
}
