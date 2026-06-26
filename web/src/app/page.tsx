"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  METRICS,
  loadYearOverlay,
  mergeOverlay,
  computeDisplayRange,
  getVisibleGeoIds,
  computeQuantileBins,
  computeQuantileBreaks,
  generateClassifiedPalette,
  stabilizeViewportBounds,
  QUANTILE_BIN_COUNT,
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

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedMetro, setSelectedMetro] = useState<string | null>(null);
  const [showTraffic, setShowTraffic] = useState(false);
  const [showRail, setShowRail] = useState(false);
  const [showBus, setShowBus] = useState(false);
  const [granularity, setGranularity] = useState<Granularity>("county");
  const [overlayIndex, setOverlayIndex] = useState<OverlayIndex | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [baseCounties, setBaseCounties] = useState<CountyData[]>([]);
  const [countyToMetro, setCountyToMetro] = useState<Record<string, string>>({});
  const [colorScaleMode, setColorScaleMode] = useState<ColorScaleMode>("viewport");
  const [selectedBins, setSelectedBins] = useState<Set<number>>(new Set());
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

  // Read URL params on mount — initializes state from external source (URL)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    const metroParam = params.get("metro");
    if (metroParam && METROS[metroParam]) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      flyToMetro(metroParam);
    }

    const metricParam = params.get("metric");
    if (metricParam) {
      const found = METRICS.find((m) => m.key === metricParam);
      if (found) setSelectedMetric(found);
    }

    const granParam = params.get("scale");
    if (granParam === "metro" || granParam === "county" || granParam === "block_group") {
      setGranularity(granParam);
    }

    const yearParam = params.get("year");
    if (yearParam) {
      setSelectedYear(Number(yearParam) || null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Write state to URL
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedMetro) params.set("metro", selectedMetro);
    if (selectedMetric.key !== METRICS[0].key) params.set("metric", selectedMetric.key);
    if (granularity !== "county") params.set("scale", granularity);
    if (selectedYear) params.set("year", String(selectedYear));

    const qs = params.toString();
    const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    window.history.replaceState(null, "", url);
  }, [selectedMetro, selectedMetric.key, granularity, selectedYear]);

  // Seed initial viewport bounds from starting viewport
  useEffect(() => {
    const span = 360 / Math.pow(2, viewport.zoom);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setViewportBounds({
      west: viewport.longitude - span / 2,
      east: viewport.longitude + span / 2,
      south: viewport.latitude - span / 4,
      north: viewport.latitude + span / 4,
    });
  }, [viewport.longitude, viewport.latitude, viewport.zoom]);

  const viewportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleViewStateChange = useCallback(
    (viewState: Record<string, unknown>) => {
      if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current);
      viewportTimerRef.current = setTimeout(() => {
        const vs = viewState as { longitude: number; latitude: number; zoom: number };
        const span = 360 / Math.pow(2, vs.zoom);
        setViewportBounds(stabilizeViewportBounds({
          west: vs.longitude - span / 2,
          east: vs.longitude + span / 2,
          south: vs.latitude - span / 4,
          north: vs.latitude + span / 4,
        }));
      }, 600);
    },
    [],
  );

  const visibleIds = useMemo(() => {
    if (colorScaleMode !== "viewport" || !viewportBounds || !geojson) return null;
    const ids = getVisibleGeoIds(geojson, viewportBounds);
    return ids.size > 0 ? ids : null;
  }, [colorScaleMode, viewportBounds, geojson]);

  const effectiveMinMax = useMemo(
    () => computeDisplayRange(counties, selectedMetric.key, visibleIds),
    [counties, selectedMetric.key, visibleIds],
  );

  const secondaryMinMax = useMemo(() => {
    if (!secondaryMetric) return null;
    return computeDisplayRange(counties, secondaryMetric.key, visibleIds);
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

  const quantileBreaks = useMemo(() => {
    if (secondaryMetric) return null;
    const source = (colorScaleMode === "viewport" && visibleIds)
      ? counties.filter(c => visibleIds.has(c.county_fips))
      : counties;
    const values = source
      .map(c => c[selectedMetric.key] as number | null)
      .filter((v): v is number => v !== null && v !== 0 && Number.isFinite(v));
    return computeQuantileBreaks(values, QUANTILE_BIN_COUNT);
  }, [counties, colorScaleMode, visibleIds, selectedMetric.key, secondaryMetric]);

  const classifiedPalette = useMemo(() => {
    if (secondaryMetric) return null;
    return generateClassifiedPalette(selectedMetric.colorScale, QUANTILE_BIN_COUNT);
  }, [selectedMetric.colorScale, secondaryMetric]);

  const displayCounties = useMemo(() => {
    if (colorScaleMode === "viewport" && visibleIds) {
      return counties.filter(c => visibleIds.has(c.county_fips));
    }
    if (selectedMetro) {
      return counties.filter(c => c.metro_id === selectedMetro);
    }
    return counties;
  }, [counties, colorScaleMode, visibleIds, selectedMetro]);

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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading external data (county-to-metro mapping)
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading external data (counties/block groups)
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
      <header className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-col gap-0.5 lg:flex-row lg:items-center lg:gap-3">
          <h1 className="font-[family-name:var(--font-display)] text-lg tracking-tight text-slate-900 dark:text-white">
            UrbanStack
          </h1>
          <div className="flex items-center gap-1.5">
            <span className="hidden text-sm text-slate-500 sm:inline dark:text-slate-400">
              Urban Data Explorer
            </span>
            <a href="https://featheranalytics.dev" target="_blank" rel="noopener noreferrer" aria-label="FeatherAnalytics website" className="text-slate-400 transition-colors hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            </a>
            <a href="https://github.com/FeatherAnalytics/urbanstack" target="_blank" rel="noopener noreferrer" aria-label="GitHub repository" className="text-slate-400 transition-colors hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            </a>
            <a href="https://www.linkedin.com/in/david-hardage/" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn profile" className="text-slate-400 transition-colors hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
            </a>
          </div>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2 lg:gap-3">
          <select
            aria-label="Select metro area"
            value={selectedMetro ?? ""}
            onChange={(e) => {
              const v = e.target.value || null;
              if (v) flyToMetro(v);
              else setSelectedMetro(null);
              setSelectedBins(new Set());
            }}
            className="rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px] text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 lg:px-2 lg:text-xs"
          >
            <option value="">All US</option>
            {Object.values(METROS).map((m) => (
              <option key={m.metro_id} value={m.metro_id}>
                {m.metro_name}
              </option>
            ))}
          </select>
          {overlayIndex && (
            <select
              aria-label="Select year"
              title="Filters Census ACS demographic and transportation metrics. Safety, spending, and congestion metrics use fixed date ranges shown in the sidebar."
              value={granularity === "county" ? (selectedYear ?? "") : ""}
              disabled={granularity !== "county"}
              onChange={(e) => {
                const v = e.target.value;
                setSelectedYear(v ? Number(v) : null);
                if (!v) setCounties(baseCounties);
              }}
              className="rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px] text-slate-700 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 lg:px-2 lg:text-xs"
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
            aria-label="Select geographic scale"
            value={granularity}
            onChange={(e) => {
              const g = e.target.value as Granularity;
              if (g === "block_group" && !selectedMetro) {
                const first = Object.keys(METROS)[0];
                flyToMetro(first);
              }
              setGranularity(g);
            }}
            className="rounded border border-slate-300 bg-white px-1.5 py-1 text-[11px] text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 lg:px-2 lg:text-xs"
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
        {/* Left sidebar — mobile overlay, desktop static */}
        <aside className={`
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          fixed inset-y-0 left-0 z-50 w-64 overflow-y-auto border-r border-slate-200 bg-white transition-transform duration-200 dark:border-slate-700 dark:bg-slate-900
          lg:static lg:z-auto lg:translate-x-0 lg:shrink-0
        `}>
          <div className="flex items-center justify-between p-3 lg:hidden">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Metrics</span>
            <button
              onClick={() => setSidebarOpen(false)}
              aria-label="Close metrics panel"
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
          <h2 className="sr-only">Metric Selection</h2>
          <MetricSelector
            selected={selectedMetric}
            onSelect={(m) => { setSelectedMetric(m); setSecondaryMetric(null); setSelectedBins(new Set()); setSidebarOpen(false); }}
            counties={counties}
            secondaryMetric={secondaryMetric}
            onSelectSecondary={(m) => { setSecondaryMetric(m); setSelectedBins(new Set()); }}
          />
        </aside>

        {/* Mobile sidebar backdrop */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Map area with floating county popup */}
        <main ref={mapRef} className="relative min-h-[300px] flex-1">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open metrics panel"
            className="absolute top-3 left-3 z-30 rounded-lg border border-slate-200/80 bg-white/90 px-3 py-1.5 text-xs font-medium text-slate-700 shadow-md backdrop-blur-sm dark:border-slate-600/80 dark:bg-slate-800/90 dark:text-slate-300 lg:hidden"
          >
            ☰ Metrics
          </button>
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
            onViewStateChange={handleViewStateChange}
            secondaryMetric={secondaryMetric}
            primaryBreaks={primaryBreaks}
            secondaryBreaks={secondaryBreaks}
            quantileBreaks={quantileBreaks}
            classifiedPalette={classifiedPalette}
            highlightedBins={selectedBins.size > 0 ? selectedBins : null}
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
              quantileBreaks={quantileBreaks}
              classifiedPalette={classifiedPalette}
              selectedBins={selectedBins}
              onSelectionChange={setSelectedBins}
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
        <h2 className="sr-only">Data Comparison</h2>
        <ComparisonChart
          counties={displayCounties}
          metric={selectedMetric}
          selectedFips={selectedFips}
          onSelect={setSelectedFips}
          granularity={granularity}
          secondaryMetric={secondaryMetric}
          primaryBreaks={primaryBreaks}
          secondaryBreaks={secondaryBreaks}
          selectedMetro={selectedMetro}
          quantileBreaks={quantileBreaks}
          classifiedPalette={classifiedPalette}
          selectedBins={selectedBins}
        />
      </div>
    </div>
  );
}
