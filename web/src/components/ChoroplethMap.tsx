"use client";

import { useCallback, useMemo } from "react";
import { Map as MapGL } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { TileLayer } from "@deck.gl/geo-layers";
import { MVTLoader } from "@loaders.gl/mvt";
import { load } from "@loaders.gl/core";
import { PMTilesTileSource } from "@loaders.gl/pmtiles";
import { ClipExtension } from "@deck.gl/extensions";
import type { Layer } from "@deck.gl/core";
import {
  interpolateColor,
  formatValue,
  classifyBin,
  getBivariateColor,
  R2_BASE_URL,
  type CountyData,
  type Granularity,
  type MetricConfig,
} from "@/lib/data";
import { METROS } from "@/lib/metro";
import "maplibre-gl/dist/maplibre-gl.css";

const BASEMAP_DARK =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const BASEMAP_LIGHT =
  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

const CLIP_EXT = new ClipExtension();

const PMTILES_SOURCES = Object.keys(METROS).map((id) => ({
  id,
  source: new PMTilesTileSource(
    `${R2_BASE_URL}/${id}_block_groups.pmtiles`,
    { core: {} },
  ),
}));

interface ChoroplethMapProps {
  geojson: GeoJSON.FeatureCollection | null;
  counties: CountyData[];
  metric: MetricConfig;
  selectedFips: string | null;
  onSelectCounty: (fips: string | null) => void;
  onHoverCounty: (county: CountyData | null, x: number, y: number) => void;
  isDark: boolean;
  granularity: Granularity;
  countyToMetro?: Record<string, string>;
  /** Additional deck.gl layers rendered on top of the choropleth */
  overlayLayers?: Layer[];
  /** Map viewport (center, zoom, pitch, bearing) — driven by metro config */
  viewport: { longitude: number; latitude: number; zoom: number; pitch: number; bearing: number };
  /** Minimum value for color scale normalization */
  minVal: number;
  /** Maximum value for color scale normalization */
  maxVal: number;
  /** Callback when viewport changes (lat, lng, zoom) */
  onViewStateChange?: (viewState: Record<string, unknown>) => void;
  secondaryMetric: MetricConfig | null;
  primaryBreaks: number[] | null;
  secondaryBreaks: number[] | null;
}

export function ChoroplethMap({
  geojson,
  counties,
  metric,
  selectedFips,
  onSelectCounty,
  onHoverCounty,
  isDark,
  granularity,
  countyToMetro = {},
  overlayLayers = [],
  viewport,
  minVal,
  maxVal,
  onViewStateChange,
  secondaryMetric,
  primaryBreaks,
  secondaryBreaks,
}: ChoroplethMapProps) {
  const isMetro = granularity === "metro";
  const isBlockGroup = granularity === "block_group";

  // Build a lookup from FIPS -> CountyData (also index by metro_id for metro view)
  const dataByFips = useMemo(() => {
    const map = new Map<string, CountyData>();
    for (const c of counties) {
      map.set(c.county_fips, c);
      if (c.metro_id) map.set(c.metro_id, c);
    }
    return map;
  }, [counties]);

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

      const rawVal = county[metric.key];
      const primaryVal = rawVal === null || rawVal === undefined ? null : Number(rawVal);
      if (primaryVal === null || !Number.isFinite(primaryVal)) return [40, 40, 40, 120];

      // Bivariate mode
      if (secondaryMetric && primaryBreaks && secondaryBreaks) {
        const secVal = county[secondaryMetric.key] as number | null;
        if (secVal === null || secVal === undefined || Number.isNaN(secVal)) return [200, 200, 200, fillAlpha];
        const pBin = classifyBin(primaryVal, primaryBreaks);
        const sBin = classifyBin(secVal, secondaryBreaks);
        return getBivariateColor(pBin, sBin, fillAlpha);
      }

      // Single-metric mode
      const range = maxVal - minVal;
      const t = range > 0 ? (primaryVal - minVal) / range : 0.5;
      const color = interpolateColor(t, metric.colorScale);
      color[3] = fillAlpha;
      return color;
    },
    [dataByFips, metric, minVal, maxVal, isMetro, counties, fillAlpha, secondaryMetric, primaryBreaks, secondaryBreaks],
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
    if (isBlockGroup) {
      return [
        ...PMTILES_SOURCES.map(({ id, source }) =>
          new TileLayer({
            id: `block-groups-${id}`,
            minZoom: 3,
            maxZoom: 12,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl tile type
            getTileData: async (tile: any) => {
              const { x, y, z } = tile.index;
              const arrayBuffer = await source.getTile({ x, y, z });
              if (!arrayBuffer) return null;
              return load(arrayBuffer, MVTLoader, {
                mvt: { coordinates: "wgs84", tileIndex: { x, y, z } },
              });
            },
            // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl subLayer props
            renderSubLayers: (props: any) => {
              if (!props.data) return null;
              const { west, south, east, north } = props.tile.bbox;
              return new GeoJsonLayer({
                ...props,
                filled: true,
                stroked: true,
                pickable: true,
                extensions: [CLIP_EXT],
                clipBounds: [west, south, east, north],
                getFillColor,
                getLineColor,
                getLineWidth,
                lineWidthUnits: "pixels" as const,
                updateTriggers: {
                  getFillColor: [metric.key, minVal, maxVal, secondaryMetric?.key, primaryBreaks, secondaryBreaks],
                  getLineColor: [selectedFips, isDark],
                  getLineWidth: [selectedFips],
                },
              });
            },
            updateTriggers: {
              renderSubLayers: [metric.key, minVal, maxVal, selectedFips, isDark, secondaryMetric?.key, primaryBreaks, secondaryBreaks],
            },
          })
        ),
        ...overlayLayers,
      ];
    }

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
          getFillColor: [metric.key, minVal, maxVal, granularity, secondaryMetric?.key, primaryBreaks, secondaryBreaks],
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
    secondaryMetric,
    primaryBreaks,
    secondaryBreaks,
    isBlockGroup,
  ]);

  const handleClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl event type
    (info: any) => {
      if (info.object) {
        const fips = info.object.properties?.GEOID as string | undefined;
        if (isMetro && fips) {
          const metroId = countyToMetro[fips];
          if (metroId) onSelectCounty(metroId);
          return;
        }
        onSelectCounty(fips ?? null);
      } else {
        onSelectCounty(null);
      }
    },
    [onSelectCounty, isMetro, countyToMetro],
  );

  const handleHover = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deck.gl event type
    (info: any) => {
      if (info.object) {
        const fips = info.object.properties?.GEOID as string | undefined;
        if (isMetro && fips) {
          const metroId = countyToMetro[fips];
          const metro = metroId ? dataByFips.get(metroId) ?? null : null;
          onHoverCounty(metro, info.x ?? 0, info.y ?? 0);
          return;
        }
        const county = fips ? dataByFips.get(fips) ?? null : null;
        onHoverCounty(county, info.x ?? 0, info.y ?? 0);
      } else {
        onHoverCounty(null, 0, 0);
      }
    },
    [dataByFips, onHoverCounty, isMetro, countyToMetro],
  );

  const basemapStyle = isDark ? BASEMAP_DARK : BASEMAP_LIGHT;

  return (
    <div className="relative h-full w-full">
      <DeckGL
        initialViewState={viewport}
        controller={true}
        layers={layers}
        onClick={handleClick}
        onHover={handleHover}
        onViewStateChange={({ viewState }) => onViewStateChange?.(viewState)}
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
  secondaryMetric?: MetricConfig | null;
  x: number;
  y: number;
  containerRef?: React.RefObject<HTMLElement | null>;
}

export function MapTooltip({ county, metric, secondaryMetric, x, y, containerRef }: MapTooltipProps) {
  if (!county) return null;

  const val = county[metric.key] as number | null;
  const secVal = secondaryMetric ? (county[secondaryMetric.key] as number | null) : null;
  // eslint-disable-next-line react-hooks/refs -- tooltip needs container rect for positioning
  const rect = containerRef?.current?.getBoundingClientRect();
  const absX = (rect?.left ?? 0) + x;
  const absY = (rect?.top ?? 0) + y;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const flipLeft = absX > vw - 260;
  const flipUp = absY > vh - 80;

  return (
    <div
      className="pointer-events-none fixed z-[9999] w-max max-w-[280px] rounded border border-slate-200 bg-white/95 px-3 py-2 text-sm shadow-lg dark:border-slate-600 dark:bg-slate-800/95"
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
      {secondaryMetric && (
        <div className="text-slate-500 dark:text-slate-400">
          {secondaryMetric.label}:{" "}
          <span className="font-mono text-slate-900 dark:text-white">
            {formatValue(secVal, secondaryMetric.format)}
          </span>
        </div>
      )}
    </div>
  );
}
