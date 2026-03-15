import { useState, useEffect, useRef } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import type { NodesPerCountry } from "../types";
import { fetchNodesPerCountry } from "../api";
import { SkeletonBlock, SkeletonStatRow } from "./Skeleton";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";
const TOOLTIP_W = 170;

function getColor(count: number, maxCount: number): string {
  if (!count) return "#1a0808";
  const t = Math.log(count + 1) / Math.log(maxCount + 1);
  const r = Math.round(0x1a + t * (0x80 - 0x1a));
  const g = Math.round(0x08 + t * (0x00 - 0x08));
  const b = Math.round(0x08 + t * (0x00 - 0x08));
  return `rgb(${r},${g},${b})`;
}

type Tooltip = { name: string; count: number; x: number; y: number } | null;

function NodesPerCountryList({ refreshKey }: { refreshKey?: number }) {
  const [nodes_per_country, setNodesPerCountry] = useState<NodesPerCountry[] | null>(null);
  const [tooltip, setTooltip] = useState<Tooltip>(null);
  const [flash, setFlash] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchNodesPerCountry().then((data) => {
      setNodesPerCountry(data);
      setFlash(true);
    });
  }, [refreshKey]);

  if (!nodes_per_country) {
    return (
      <div className="card map-card">
        <h2>Nodes by Country</h2>
        <SkeletonBlock width="100%" height={200} />
        <SkeletonStatRow /><SkeletonStatRow /><SkeletonStatRow />
        <SkeletonStatRow /><SkeletonStatRow />
      </div>
    );
  }

  const byName = Object.fromEntries(
    nodes_per_country.flatMap((c) => {
      const entries: [string, typeof c][] = [];
      if (c.name?.en) entries.push([c.name.en.toLowerCase(), c]);
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
  const top10 = [...nodes_per_country].sort((a, b) => b.count - a.count).slice(0, 10);

  function relativePos(clientX: number, clientY: number) {
    const rect = wrapperRef.current?.getBoundingClientRect();
    if (!rect) return { x: clientX, y: clientY };
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  const tooltipX = tooltip
    ? Math.min(tooltip.x + 12, (wrapperRef.current?.offsetWidth ?? 9999) - TOOLTIP_W - 4)
    : 0;

  return (
    <div className={`card map-card${flash ? " card--flash" : ""}`}>
      <h2>Nodes by Country</h2>
      <div className="map-wrapper" ref={wrapperRef} onMouseLeave={() => setTooltip(null)}>
        <ComposableMap
          projectionConfig={{ scale: 130, center: [0, 0] }}
          width={800}
          height={340}
          style={{ width: "100%", height: "auto" }}
        >
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
                      setTooltip({ name, count, ...relativePos(e.clientX, e.clientY) });
                    }}
                    onMouseMove={(e) => {
                      if (!count) return;
                      setTooltip((t) => t ? { ...t, ...relativePos(e.clientX, e.clientY) } : t);
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
            style={{ left: tooltipX, top: tooltip.y - 36, position: "absolute" }}
          >
            <span className="map-tooltip-name">{tooltip.name}</span>
            <span className="map-tooltip-count">{tooltip.count.toLocaleString()} nodes</span>
          </div>
        )}
      </div>

      {/* ── Top 10 legend ── */}
      <div className="map-legend">
        {top10.map((country, i) => (
          <div key={country.iso ?? country.name?.en} className="map-legend-item">
            <span className="map-legend-rank">#{i + 1}</span>
            <span
              className="map-legend-swatch"
              style={{ background: getColor(country.count, maxCount) }}
            />
            <span className="map-legend-name">{country.name?.en ?? "—"}</span>
            <span className="map-legend-count">{country.count.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default NodesPerCountryList;
