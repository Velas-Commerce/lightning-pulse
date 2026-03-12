import { useState, useEffect } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import type { NodesPerCountry } from "../types";
import { fetchNodesPerCountry } from "../api";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Interpolate from dark card bg to #800000 on a log scale
function getColor(count: number, maxCount: number): string {
  if (!count) return "#1a0808";
  const t = Math.log(count + 1) / Math.log(maxCount + 1);
  // blend #1a0808 → #800000
  const r = Math.round(0x1a + t * (0x80 - 0x1a));
  const g = Math.round(0x08 + t * (0x00 - 0x08));
  const b = Math.round(0x08 + t * (0x00 - 0x08));
  return `rgb(${r},${g},${b})`;
}

type Tooltip = { name: string; count: number; x: number; y: number } | null;

function NodesPerCountryList() {
  const [nodes_per_country, setNodesPerCountry] = useState<NodesPerCountry[] | null>(null);
  const [tooltip, setTooltip] = useState<Tooltip>(null);

  useEffect(() => {
    fetchNodesPerCountry().then((data) => setNodesPerCountry(data));
  }, []);

  if (!nodes_per_country) {
    return (
      <div className="card map-card">
        <h2>Nodes by Country</h2>
      </div>
    );
  }

  // world-atlas topojson has no ISO_A2 — match by English name (lowercase)
  const byName = Object.fromEntries(
    nodes_per_country.flatMap((c) => {
      const entries: [string, typeof c][] = [];
      if (c.name?.en) entries.push([c.name.en.toLowerCase(), c]);
      // API name → topojson name for confirmed mismatches
      const overrides: Record<string, string> = {
        "united states": "united states of america",
        "bosnia and herzegovina": "bosnia and herz.",
      };
      const key = c.name?.en?.toLowerCase() ?? "";
      if (overrides[key]) entries.push([overrides[key], c]);
      return entries;
    })
  );
  const maxCount = Math.max(...nodes_per_country.map((c) => c.count));

  return (
    <div className="card map-card">
      <h2>Nodes by Country</h2>
      <div className="map-wrapper" onMouseLeave={() => setTooltip(null)}>
        <ComposableMap projectionConfig={{ scale: 140 }} style={{ width: "100%", height: "auto" }}>
          <Geographies geography={GEO_URL}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const geoName: string = geo.properties.name?.toLowerCase() ?? "";
                const data = byName[geoName];
                const count = data?.count ?? 0;
                const fill = getColor(count, maxCount);
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={fill}
                    stroke="#2a0c08"
                    strokeWidth={0.4}
                    style={{
                      default: { outline: "none" },
                      hover: { outline: "none", fill: count ? "#c04000" : "#2a1008", cursor: count ? "pointer" : "default" },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={(e) => {
                      if (!count) return;
                      const name = data?.name?.en ?? geo.properties.name ?? geoName;
                      setTooltip({ name, count, x: e.clientX, y: e.clientY });
                    }}
                    onMouseMove={(e) => {
                      if (!count) return;
                      setTooltip((t) => t ? { ...t, x: e.clientX, y: e.clientY } : t);
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                );
              })
            }
          </Geographies>
        </ComposableMap>

        {tooltip && (
          <div
            className="map-tooltip"
            style={{ left: tooltip.x + 12, top: tooltip.y - 36, position: "fixed" }}
          >
            <span className="map-tooltip-name">{tooltip.name}</span>
            <span className="map-tooltip-count">{tooltip.count.toLocaleString()} nodes</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default NodesPerCountryList;
