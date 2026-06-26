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
  showFerry: boolean;
  onToggleFerry: () => void;
  hasMetroSelected: boolean;
  hasRail: boolean;
  hasBus: boolean;
  hasFerry: boolean;
}

export function MapControls({
  showTraffic,
  onToggleTraffic,
  showRail,
  onToggleRail,
  showBus,
  onToggleBus,
  showFerry,
  onToggleFerry,
  hasMetroSelected,
  hasRail,
  hasBus,
  hasFerry,
}: MapControlsProps) {
  return (
    <div className="absolute bottom-3 left-3 z-30 flex gap-1.5 rounded-lg border border-slate-200/80 bg-white/70 p-1 shadow-md backdrop-blur-sm dark:border-slate-600/80 dark:bg-slate-800/70">
      <TrafficToggle enabled={showTraffic} onToggle={onToggleTraffic} />
      {hasMetroSelected && (
        <TransitToggles
          railEnabled={showRail}
          busEnabled={showBus}
          ferryEnabled={showFerry}
          onToggleRail={onToggleRail}
          onToggleBus={onToggleBus}
          onToggleFerry={onToggleFerry}
          railAvailable={hasRail}
          busAvailable={hasBus}
          ferryAvailable={hasFerry}
        />
      )}
    </div>
  );
}
