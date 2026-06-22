"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  METRICS,
  loadData,
  loadGeoJSON,
  loadOverlayIndex,
  loadYearOverlay,
  mergeOverlay,
  computeMinMax,
  getVisibleGeoIds,
  type ColorScaleMode,
  type ViewportBounds,
  type CountyData,
  type Granularity,
  type MetricConfig,
  type OverlayIndex,
} from "@/lib/data";
import { METROS, DEFAULT_METRO } from "@/lib/metro";
import { MetricSelector } from "@/components/MetricSelector";
import { CountyDetailPopup } from "@/components/CountyDetail";
import { ComparisonChart } from "@/components/ComparisonChart";
import { ChoroplethMap, MapTooltip } from "@/components/ChoroplethMap";
import { ThemeToggle, useTheme } from "@/components/ThemeToggle";
import { MapControls } from "@/components/MapControls";
import { useTrafficLayer } from "@/components/TrafficLayer";
import { useTransitLayers } from "@/components/TransitLayer";
import { ColorLegend } from "@/components/ColorLegend";

export default function Home() {
  const [counties, setCounties] = useState<CountyData[]>([]);
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(
    null,
  );
  const [selectedMetric, setSelectedMetric] = useState<MetricConfig>(
    METRICS[0],
  );
  const [selectedFips, setSelectedFips] = useState<string | null>(null);
  const [hoverCounty, setHoverCounty] = useState<CountyData | null>(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedMetro, setSelectedMetro] = useState(DEFAULT_METRO);
  const [showTraffic, setShowTraffic] = useState(false);
  const [showRail, setShowRail] = useState(false);
  const [showBus, setShowBus] = useState(false);
  const [granularity, setGranularity] = useState<Granularity>("county");
  const [overlayIndex, setOverlayIndex] = useState<OverlayIndex | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [baseCounties, setBaseCounties] = useState<CountyData[]>([]);
  const [colorScaleMode, setColorScaleMode] = useState<ColorScaleMode>("global");
  const [viewportBounds, setViewportBounds] = useState<ViewportBounds | null>(null);

  const yearRef = useRef<number | null>(null);
  const { isDark, toggle } = useTheme();

  const transitModes = useMemo(() => {
    const modes = new Set<"rail" | "bus">();
    if (showRail) modes.add("rail");
    if (showBus) modes.add("bus");
    return modes;
  }, [showRail, showBus]);

  const trafficLayer = useTrafficLayer(showTraffic);
  const transitLayers = useTransitLayers(transitModes, selectedMetro);

  const viewport = useMemo(() => {
    const m = METROS[selectedMetro] ?? METROS[DEFAULT_METRO];
    return { longitude: m.center[1], latitude: m.center[0], zoom: m.zoom, pitch: 0, bearing: 0 };
  }, [selectedMetro]);

  const viewportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleViewStateChange = useCallback(
    (viewState: Record<string, unknown>) => {
      if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current);
      viewportTimerRef.current = setTimeout(() => {
        const vs = viewState as { longitude: number; latitude: number; zoom: number };
        const span = 360 / Math.pow(2, vs.zoom);
        setViewportBounds({
          west: vs.longitude - span / 2,
          east: vs.longitude + span / 2,
          south: vs.latitude - span / 4,
          north: vs.latitude + span / 4,
        });
      }, 300);
    },
    [],
  );

  const effectiveMinMax = useMemo(() => {
    if (colorScaleMode === "viewport" && viewportBounds && geojson) {
      const visibleIds = getVisibleGeoIds(geojson, viewportBounds);
      if (visibleIds.size > 0) {
        return computeMinMax(counties, selectedMetric.key, visibleIds);
      }
    }
    return computeMinMax(counties, selectedMetric.key, null);
  }, [colorScaleMode, viewportBounds, geojson, counties, selectedMetric.key]);

  const overlayLayers = useMemo(() => {
    const out = [];
    if (trafficLayer) out.push(trafficLayer);
    out.push(...transitLayers);
    return out;
  }, [trafficLayer, transitLayers]);

  useEffect(() => {
    loadOverlayIndex(selectedMetro).then((idx) => {
      setOverlayIndex(idx);
      if (idx && idx.years.length > 0) {
        setSelectedYear(idx.years[idx.years.length - 1]);
      }
    });
  }, [selectedMetro]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setSelectedFips(null);
    setSelectedYear(null);
    Promise.all([loadData(selectedMetro, granularity), loadGeoJSON(selectedMetro, granularity)])
      .then(([data, geo]) => {
        setBaseCounties(data);
        setCounties(data);
        setGeojson(geo);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (granularity !== "county") {
          Promise.all([loadData(selectedMetro, "county"), loadGeoJSON(selectedMetro, "county")])
            .then(([data, geo]) => {
              setBaseCounties(data);
              setCounties(data);
              setGeojson(geo);
              setGranularity("county");
              setLoading(false);
            })
            .catch((fallbackErr: unknown) => {
              const msg =
                fallbackErr instanceof Error
                  ? fallbackErr.message
                  : "Failed to load data";
              setError(msg);
              setLoading(false);
            });
        } else {
          const msg =
            err instanceof Error ? err.message : "Failed to load data";
          setError(msg);
          setLoading(false);
        }
      });
  }, [selectedMetro, granularity]);

  useEffect(() => {
    if (!selectedYear || granularity !== "county") return;
    yearRef.current = selectedYear;
    loadYearOverlay(selectedMetro, selectedYear).then((overlay) => {
      if (overlay && yearRef.current === selectedYear) {
        setCounties(mergeOverlay(baseCounties, overlay));
      }
    });
  }, [selectedMetro, selectedYear, baseCounties, granularity]);

  const mapRef = useRef<HTMLElement>(null);

  const selectedCounty =
    counties.find((c) => c.county_fips === selectedFips) ?? null;

  const handleHover = useCallback(
    (county: CountyData | null, x: number, y: number) => {
      setHoverCounty(county);
      setHoverPos({ x, y });
    },
    [],
  );

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
        Loading data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-red-600 dark:bg-slate-900 dark:text-red-400">
        {error}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-slate-50 dark:bg-slate-900">
      {/* Header */}
      <header className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-700 dark:bg-slate-900">
        <h1 className="text-base font-semibold text-slate-900 dark:text-white">
          UrbanStack
        </h1>
        <span className="text-sm text-slate-500 dark:text-slate-400">
          {METROS[selectedMetro]?.metro_name ?? "Urban Data"} Explorer
        </span>
        <div className="ml-auto flex items-center gap-3">
          <select
            value={selectedMetro}
            onChange={(e) => {
              setSelectedMetro(e.target.value);
              setSelectedFips(null);
              setOverlayIndex(null);
              setSelectedYear(null);
            }}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
            aria-label="Select metro area"
          >
            {Object.entries(METROS).map(([id, config]) => (
              <option key={id} value={id}>
                {config.metro_name}
              </option>
            ))}
          </select>
          {overlayIndex && granularity === "county" && (
            <select
              value={selectedYear ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setSelectedYear(v ? Number(v) : null);
                if (!v) setCounties(baseCounties);
              }}
              className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
            >
              <option value="">All Years (Cumulative)</option>
              {overlayIndex.years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          )}
          <select
            value={granularity}
            onChange={(e) => setGranularity(e.target.value as Granularity)}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
          >
            <option value="metro">Metro Area</option>
            <option value="county">County</option>
            <option value="block_group">Block Group</option>
          </select>
          <ThemeToggle isDark={isDark} onToggle={toggle} />
        </div>
      </header>

      {/* Main content: sidebar + map */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Left sidebar — metric selector only */}
        <aside className="shrink-0 overflow-y-auto border-b border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 lg:w-64 lg:border-b-0 lg:border-r">
          <div className="max-h-48 overflow-y-auto lg:max-h-none">
            <MetricSelector
              selected={selectedMetric}
              onSelect={setSelectedMetric}
              counties={counties}
            />
          </div>
        </aside>

        {/* Map area with floating county popup */}
        <main ref={mapRef} className="relative min-h-[300px] flex-1">
          <ChoroplethMap
            key={selectedMetro}
            geojson={geojson}
            counties={counties}
            metric={selectedMetric}
            selectedFips={selectedFips}
            onSelectCounty={setSelectedFips}
            onHoverCounty={handleHover}
            isDark={isDark}
            granularity={granularity}
            overlayLayers={overlayLayers}
            viewport={viewport}
            minVal={effectiveMinMax.min}
            maxVal={effectiveMinMax.max}
            onViewStateChange={handleViewStateChange}
          />
          <MapTooltip
            county={hoverCounty}
            metric={selectedMetric}
            x={hoverPos.x}
            y={hoverPos.y}
            containerRef={mapRef}
          />
          <MapControls
            showTraffic={showTraffic}
            onToggleTraffic={() => setShowTraffic((v) => !v)}
            showRail={showRail}
            onToggleRail={() => setShowRail((v) => !v)}
            showBus={showBus}
            onToggleBus={() => setShowBus((v) => !v)}
          />
          <div className="absolute left-[calc(theme(spacing.64)+0.75rem)] top-3 z-30 lg:left-[calc(16rem+0.75rem)]">
            <ColorLegend
              primaryMetric={selectedMetric}
              secondaryMetric={null}
              primaryMinMax={effectiveMinMax}
              secondaryMinMax={null}
              colorScaleMode={colorScaleMode}
              onToggleMode={() => setColorScaleMode((m) => (m === "global" ? "viewport" : "global"))}
              granularity={granularity}
            />
          </div>
          <CountyDetailPopup
            county={selectedCounty}
            allCounties={counties}
            selectedMetric={selectedMetric}
            onClose={() => setSelectedFips(null)}
          />
        </main>
      </div>

      {/* Bottom comparison chart */}
      <div className="shrink-0 overflow-y-auto border-t border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 lg:max-h-72">
        <ComparisonChart
          counties={counties}
          metric={selectedMetric}
          selectedFips={selectedFips}
          onSelect={setSelectedFips}
          granularity={granularity}
        />
      </div>
    </div>
  );
}
