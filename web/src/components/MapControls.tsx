"use client";

import { TrafficToggle } from "./TrafficLayer";
import { TransitToggles } from "./TransitLayer";

interface MapControlsProps {
  showTraffic: boolean;
  onToggleTraffic: () => void;
  showRail: boolean;
  onToggleRail: () => void;
  showBus: boolean;
  onToggleBus: () => void;
}

export function MapControls({
  showTraffic,
  onToggleTraffic,
  showRail,
  onToggleRail,
  showBus,
  onToggleBus,
}: MapControlsProps) {
  return (
    <div className="absolute bottom-3 left-3 z-30 flex gap-1.5 rounded-lg border border-slate-200/80 bg-white/70 p-1 shadow-md backdrop-blur-sm dark:border-slate-600/80 dark:bg-slate-800/70">
      <TrafficToggle enabled={showTraffic} onToggle={onToggleTraffic} />
      <TransitToggles
        railEnabled={showRail}
        busEnabled={showBus}
        onToggleRail={onToggleRail}
        onToggleBus={onToggleBus}
      />
    </div>
  );
}
