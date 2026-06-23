"use client";

import { useEffect, useState } from "react";
import { TileLayer } from "@deck.gl/geo-layers";
import { BitmapLayer } from "@deck.gl/layers";

const TOMTOM_API_KEY = process.env.NEXT_PUBLIC_TOMTOM_API_KEY ?? "";

export function useTrafficLayer(enabled: boolean) {
  const [cacheBuster, setCacheBuster] = useState(0);

  useEffect(() => {
    if (!enabled) return;

    const interval = setInterval(() => {
      if (!document.hidden) setCacheBuster(Date.now());
    }, 5 * 60 * 1000);

    const handleVisibility = () => {
      if (!document.hidden) setCacheBuster(Date.now());
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [enabled]);

  if (!enabled || !TOMTOM_API_KEY) return null;

  return new TileLayer({
    id: "traffic-tiles",
    data: `https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x}/{y}.png?key=${TOMTOM_API_KEY}&tileSize=256&_t=${cacheBuster}`,
    minZoom: 0,
    maxZoom: 18,
    tileSize: 256,
    renderSubLayers: (props) => {
      const { boundingBox } = props.tile;
      return new BitmapLayer(props, {
        data: undefined,
        image: props.data,
        bounds: [
          boundingBox[0][0],
          boundingBox[0][1],
          boundingBox[1][0],
          boundingBox[1][1],
        ],
      });
    },
    updateTriggers: {
      data: [cacheBuster],
    },
  });
}

interface TrafficToggleProps {
  enabled: boolean;
  onToggle: () => void;
}

export function TrafficToggle({ enabled, onToggle }: TrafficToggleProps) {
  return (
    <button
      onClick={onToggle}
      title={enabled ? "Hide traffic" : "Show traffic"}
      aria-label={enabled ? "Hide traffic layer" : "Show traffic layer"}
      className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
        enabled
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
        <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />
        <circle cx="7" cy="17" r="2" />
        <path d="M9 17h6" />
        <circle cx="17" cy="17" r="2" />
      </svg>
      Traffic
    </button>
  );
}
