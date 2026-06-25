"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  METRICS,
  loadYearOverlay,
  mergeOverlay,
  computeMinMax,
  getVisibleGeoIds,
  computeQuantileBins,
  loadData,
  loadGeoJSON,
  loadAllData,
  loadAllGeoJSON,
  loadAllOverlayIndexes,
  type ColorScaleMode,
  type ViewportBounds,
  type CountyData,
  type Granularity,
  type MetricConfig,
  type OverlayIndex,
} from "@/lib/data";
import { METROS } from "@/lib/metro";
import { MetricSelector } from "@/components/MetricSelector";
import { CountyDetailPopup } from "@/components/CountyDetail";
import { ComparisonChart } from "@/components/ComparisonChart";
import { ChoroplethMap, MapTooltip } from "@/components/ChoroplethMap";
import { ThemeToggle, useTheme } from "@/components/ThemeToggle";
import { MapControls } from "@/components/MapControls";
import { useTrafficLayer } from "@/components/TrafficLayer";
import { useTransitLayers } from "@/components/TransitLayer";
import { TransitLegend } from "@/components/TransitLegend";
import { ColorLegend } from "@/components/ColorLegend";

export default function Home() {
  const [counties, setCounties] = useState<CountyData[]>([]);
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(
    null,
  );
  const [selectedMetric, setSelectedMetric] = useState<MetricConfig>(
    METRICS[0],
  );
  const [secondaryMetric, setSecondaryMetric] = useState<MetricConfig | null>(null);
  const [selectedFips, setSelectedFips] = useState<string | null>(null);
  const [hoverCounty, setHoverCounty] = useState<CountyData | null>(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedMetro, setSelectedMetro] = useState<string | null>(null);
  const [showTraffic, setShowTraffic] = useState(false);
  const [showRail, setShowRail] = useState(false);
  const [showBus, setShowBus] = useState(false);
  const [granularity, setGranularity] = useState<Granularity>("county");
  const [overlayIndex, setOverlayIndex] = useState<OverlayIndex | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [baseCounties, setBaseCounties] = useState<CountyData[]>([]);
  const [countyToMetro, setCountyToMetro] = useState<Record<string, string>>({});
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
  const { layers: transitLayers, routes: transitRoutes, availableModes: transitModeAvail } = useTransitLayers(transitModes, selectedMetro);

  const [viewport, setViewport] = useState({
    longitude: -92.0,
    latitude: 37.5,
    zoom: 5,
    pitch: 0,
    bearing: 0,
  });
  const [viewportKey, setViewportKey] = useState(0);

  const flyToMetro = useCallback((metroId: string) => {
    const metro = METROS[metroId];
    if (!metro) return;
    setSelectedMetro(metroId);
    setViewport({
      longitude: metro.center[1],
      latitude: metro.center[0],
      zoom: metro.zoom,
      pitch: 0,
      bearing: 0,
    });
    setViewportKey((k) => k + 1);
  }, []);

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

  const visibleIds = useMemo(() => {
    if (colorScaleMode !== "viewport" || !viewportBounds || !geojson) return null;
    const ids = getVisibleGeoIds(geojson, viewportBounds);
    return ids.size > 0 ? ids : null;
  }, [colorScaleMode, viewportBounds, geojson]);

  const effectiveMinMax = useMemo(
    () => computeMinMax(counties, selectedMetric.key, visibleIds),
    [counties, selectedMetric.key, visibleIds],
  );

  const secondaryMinMax = useMemo(() => {
    if (!secondaryMetric) return null;
    return computeMinMax(counties, secondaryMetric.key, visibleIds);
  }, [secondaryMetric, counties, visibleIds]);

  const primaryBreaks = useMemo(() => {
    if (!secondaryMetric) return null;
    const values = counties
      .map((c) => c[selectedMetric.key] as number | null)
      .filter((v): v is number => v !== null && !Number.isNaN(v));
    return computeQuantileBins(values, 3);
  }, [counties, selectedMetric.key, secondaryMetric]);

  const secondaryBreaks = useMemo(() => {
    if (!secondaryMetric) return null;
    const values = counties
      .map((c) => c[secondaryMetric.key] as number | null)
      .filter((v): v is number => v !== null && !Number.isNaN(v));
    return computeQuantileBins(values, 3);
  }, [counties, secondaryMetric]);

  const overlayLayers = useMemo(() => {
    const out = [];
    if (trafficLayer) out.push(trafficLayer);
    out.push(...transitLayers);
    return out;
  }, [trafficLayer, transitLayers]);

  useEffect(() => {
    if (granularity !== "county" && granularity !== "metro") return;
    const map: Record<string, string> = {};
    for (const c of baseCounties) {
      const mid = c.metro_id;
      if (mid) map[c.county_fips] = mid;
    }
    if (Object.keys(map).length > 0) setCountyToMetro(map);
  }, [baseCounties, granularity]);

  useEffect(() => {
    loadAllOverlayIndexes().then((indexes) => {
      const allYears = new Set<number>();
      for (const idx of Object.values(indexes)) {
        for (const y of idx.years) allYears.add(y);
      }
      const years = [...allYears].sort();
      if (years.length > 0) {
        setOverlayIndex({ years });
        setSelectedYear(years[years.length - 1]);
      }
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setSelectedFips(null);
    setSelectedYear(null);

    if (granularity === "block_group") {
      if (!selectedMetro) {
        setLoading(false);
        return;
      }
      Promise.all([loadData(selectedMetro, "block_group"), loadGeoJSON(selectedMetro, "block_group")])
        .then(([data, geo]) => {
          setBaseCounties(data);
          setCounties(data);
          setGeojson(geo);
          setLoading(false);
        })
        .catch((err) => {
          console.error("Failed to load block groups:", err);
          setGranularity("county");
          setLoading(false);
        });
    } else {
      // County/metro: load both GeoJSON and attribute data as before
      Promise.all([loadAllData(granularity), loadAllGeoJSON(granularity)])
        .then(([data, geo]) => {
          setBaseCounties(data);
          setCounties(data);
          setGeojson(geo);
          setLoading(false);
        })
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : "Failed to load data";
          setError(msg);
          setLoading(false);
        });
    }
  }, [granularity, selectedMetro]);

  useEffect(() => {
    if (!selectedYear || granularity !== "county") return;
    yearRef.current = selectedYear;
    const metroIds = Object.keys(METROS);
    Promise.allSettled(
      metroIds.map((id) => loadYearOverlay(id, selectedYear))
    ).then((results) => {
      if (yearRef.current !== selectedYear) return;
      const allOverlay = results
        .filter((r): r is PromiseFulfilledResult<Record<string, Partial<CountyData>>> =>
          r.status === "fulfilled" && r.value != null)
        .reduce<Record<string, Partial<CountyData>>>((acc, r) => ({ ...acc, ...r.value }), {});
      if (Object.keys(allOverlay).length > 0) {
        setCounties(mergeOverlay(baseCounties, allOverlay));
      }
    });
  }, [selectedYear, baseCounties, granularity]);

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
          Urban Data Explorer
        </span>
        <div className="ml-auto flex items-center gap-3">
          <select
            value={selectedMetro ?? ""}
            onChange={(e) => {
              const v = e.target.value || null;
              if (v) flyToMetro(v);
              else setSelectedMetro(null);
            }}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
          >
            <option value="">All US</option>
            {Object.values(METROS).map((m) => (
              <option key={m.metro_id} value={m.metro_id}>
                {m.metro_name}
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
            onChange={(e) => {
              const g = e.target.value as Granularity;
              if (g === "block_group" && !selectedMetro) {
                const first = Object.keys(METROS)[0];
                flyToMetro(first);
              }
              setGranularity(g);
            }}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
          >
            <option value="metro">Metro Area</option>
            <option value="county">County</option>
            <option value="block_group">
              Block Group{selectedMetro ? "" : " (select metro)"}
            </option>
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
              onSelect={(m) => { setSelectedMetric(m); setSecondaryMetric(null); }}
              counties={counties}
              secondaryMetric={secondaryMetric}
              onSelectSecondary={setSecondaryMetric}
            />
          </div>
        </aside>

        {/* Map area with floating county popup */}
        <main ref={mapRef} className="relative min-h-[300px] flex-1">
          <ChoroplethMap
            key={viewportKey}
            geojson={geojson}
            counties={counties}
            metric={selectedMetric}
            selectedFips={selectedFips}
            onSelectCounty={setSelectedFips}
            onHoverCounty={handleHover}
            isDark={isDark}
            granularity={granularity}
            countyToMetro={countyToMetro}
            overlayLayers={overlayLayers}
            viewport={viewport}
            minVal={effectiveMinMax.min}
            maxVal={effectiveMinMax.max}
            onViewStateChange={colorScaleMode === "viewport" ? handleViewStateChange : undefined}
            secondaryMetric={secondaryMetric}
            primaryBreaks={primaryBreaks}
            secondaryBreaks={secondaryBreaks}
          />
          <MapTooltip
            county={hoverCounty}
            metric={selectedMetric}
            secondaryMetric={secondaryMetric}
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
            hasMetroSelected={selectedMetro !== null}
            hasRail={transitModeAvail.rail}
            hasBus={transitModeAvail.bus}
          />
          <TransitLegend routes={transitRoutes} />
          <div className="absolute left-1 top-3 z-30 lg:left-1">
            <ColorLegend
              primaryMetric={selectedMetric}
              secondaryMetric={secondaryMetric}
              primaryMinMax={effectiveMinMax}
              secondaryMinMax={secondaryMinMax}
              colorScaleMode={colorScaleMode}
              onToggleMode={() => setColorScaleMode((m) => (m === "global" ? "viewport" : "global"))}
              onExitCompare={() => setSecondaryMetric(null)}
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
          secondaryMetric={secondaryMetric}
          primaryBreaks={primaryBreaks}
          secondaryBreaks={secondaryBreaks}
        />
      </div>
    </div>
  );
}
