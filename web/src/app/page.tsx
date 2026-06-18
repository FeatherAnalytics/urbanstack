"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  METRICS,
  loadData,
  loadGeoJSON,
  type CountyData,
  type Granularity,
  type MetricConfig,
} from "@/lib/data";
import { MetricSelector } from "@/components/MetricSelector";
import { CountyDetailPopup } from "@/components/CountyDetail";
import { ComparisonChart } from "@/components/ComparisonChart";
import { DFWMap, MapTooltip } from "@/components/DFWMap";
import { ThemeToggle, useTheme } from "@/components/ThemeToggle";
import { MapControls } from "@/components/MapControls";
import { useTrafficLayer } from "@/components/TrafficLayer";
import { useTransitLayers } from "@/components/TransitLayer";

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

  const [showTraffic, setShowTraffic] = useState(false);
  const [showRail, setShowRail] = useState(false);
  const [showBus, setShowBus] = useState(false);
  const [granularity, setGranularity] = useState<Granularity>("county");

  const { isDark, toggle } = useTheme();

  const transitModes = useMemo(() => {
    const modes = new Set<"rail" | "bus">();
    if (showRail) modes.add("rail");
    if (showBus) modes.add("bus");
    return modes;
  }, [showRail, showBus]);

  const trafficLayer = useTrafficLayer(showTraffic);
  const transitLayers = useTransitLayers(transitModes);

  const overlayLayers = useMemo(() => {
    const out = [];
    if (trafficLayer) out.push(trafficLayer);
    out.push(...transitLayers);
    return out;
  }, [trafficLayer, transitLayers]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setSelectedFips(null);
    Promise.all([loadData(granularity), loadGeoJSON(granularity)])
      .then(([data, geo]) => {
        setCounties(data);
        setGeojson(geo);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (granularity !== "county") {
          Promise.all([loadData("county"), loadGeoJSON("county")])
            .then(([data, geo]) => {
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
  }, [granularity]);

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
        Loading DFW data...
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
          DFW Urban Data Explorer
        </span>
        <div className="ml-auto flex items-center gap-3">
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
          <DFWMap
            geojson={geojson}
            counties={counties}
            metric={selectedMetric}
            selectedFips={selectedFips}
            onSelectCounty={setSelectedFips}
            onHoverCounty={handleHover}
            isDark={isDark}
            granularity={granularity}
            overlayLayers={overlayLayers}
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
