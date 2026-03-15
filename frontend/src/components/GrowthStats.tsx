import { useState, useEffect } from "react";
import type { LightningGrowthStats, BtcPrice, MonthlyVolumeEntry } from "../types";
import { fetchGrowthStats, fetchBtcPrice } from "../api";
import { SkeletonStatRow } from "./Skeleton";

// ── Volume Bar Chart ──────────────────────────────────────────────────────────
function VolumeChart({ data }: { data: MonthlyVolumeEntry[] }) {
  const W = 320, H = 175;
  const PAD_T = 26, PAD_B = 44, PAD_L = 8, PAD_R = 8;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const BAR_W = 48;
  const n = data.length;
  const slotW = plotW / n;

  // Log scale so all four bars are readable despite the 97× range
  const logVals = data.map((d) => Math.log10(d.volume_usd));
  const minLog = Math.min(...logVals);
  const maxLog = Math.max(...logVals);
  function barH(val: number) {
    return ((Math.log10(val) - minLog) / (maxLog - minLog)) * plotH;
  }

  // Animate bars growing from baseline on mount
  const [animT, setAnimT] = useState(0);
  useEffect(() => {
    const duration = 1200;
    const start = performance.now();
    function frame(now: number) {
      const t = Math.min((now - start) / duration, 1);
      setAnimT(1 - Math.pow(1 - t, 3));
      if (t < 1) requestAnimationFrame(frame);
    }
    const id = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(id);
  }, [data]);

  function fmt(v: number) {
    if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
    return `$${(v / 1_000_000).toFixed(1)}M`;
  }

  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const baseline = PAD_T + plotH;

  // Dashed trend line connecting bar tops
  const trendPoints = data.map((d, i) => {
    const h = barH(d.volume_usd) * animT;
    const cx = PAD_L + slotW * i + slotW / 2;
    return `${cx.toFixed(1)},${(baseline - h).toFixed(1)}`;
  }).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }}>
      <defs>
        <filter id="bar-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Baseline */}
      <line x1={PAD_L} y1={baseline} x2={W - PAD_R} y2={baseline}
        stroke="#2a0c08" strokeWidth={1} />

      {data.map((entry, i) => {
        const h = barH(entry.volume_usd) * animT;
        const cx = PAD_L + slotW * i + slotW / 2;
        const bx = cx - BAR_W / 2;
        const by = baseline - h;
        const hovered = hoveredIdx === i;

        return (
          <g key={entry.date}
            onMouseEnter={() => setHoveredIdx(i)}
            onMouseLeave={() => setHoveredIdx(null)}
            style={{ cursor: "default" }}>

            {/* Bar */}
            <rect x={bx} y={by} width={BAR_W} height={h}
              fill={hovered ? "#a03000" : "#6a0000"} rx={3}
              filter={hovered ? "url(#bar-glow)" : undefined}
              style={{ transition: "fill 0.15s" }}
            />

            {/* Value label above bar */}
            <text x={cx} y={by - 5} textAnchor="middle"
              fill={hovered ? "var(--text)" : "var(--text-dim)"}
              fontSize="9.5" fontWeight="600"
              style={{ transition: "fill 0.15s" }}>
              {fmt(entry.volume_usd)}
            </text>

            {/* Date label */}
            <text x={cx} y={baseline + 13} textAnchor="middle"
              fill={hovered ? "var(--text-dim)" : "#5a2810"} fontSize="8.5"
              style={{ transition: "fill 0.15s" }}>
              {entry.date}
            </text>

            {/* Txns on hover */}
            <text x={cx} y={baseline + 25} textAnchor="middle"
              fill="var(--text-dim)" fontSize="7.5"
              opacity={hovered ? 1 : 0}
              style={{ transition: "opacity 0.15s" }}>
              {entry.transactions.toLocaleString()} txns
            </text>
          </g>
        );
      })}

      {/* Trend line — fades in after bars are mostly drawn */}
      <polyline points={trendPoints}
        fill="none" stroke="var(--amber)" strokeWidth={1.5}
        strokeDasharray="4 3" opacity={animT > 0.6 ? 0.55 : 0}
        style={{ transition: "opacity 0.4s" }}
      />

      {/* Log scale note */}
      <text x={W - PAD_R} y={H - 3} textAnchor="end"
        fill="#3a1010" fontSize="7">
        log scale
      </text>
    </svg>
  );
}

function GrowthStats({ refreshKey }: { refreshKey?: number }) {
  const [growth_stats, setGrowthStats] = useState<LightningGrowthStats | null>(null);
  const [price, setPrice] = useState<BtcPrice | null>(null);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    fetchGrowthStats().then((data) => setGrowthStats(data));
    fetchBtcPrice().then((data) => {
      setPrice(data);
      setFlash(true);
    });
  }, [refreshKey]);

  return (
    <div className={`card${flash ? " card--flash" : ""}`}>
      <h2>Market &amp; Growth</h2>
      {price ? (
        <>
          <p><span>BTC Price</span><span className="val">${price.USD.toLocaleString()} USD</span></p>
          <p><span>Sats per Dollar</span><span className="val">{Math.round(100_000_000 / price.USD).toLocaleString()} sats</span></p>
        </>
      ) : (
        <>
          <SkeletonStatRow />
          <SkeletonStatRow valWidth="22%" />
        </>
      )}
      {growth_stats ? (
        <>
          <p><span>Users with Access</span><span className="val">{growth_stats.num_lightning_users.toLocaleString()}</span></p>
          <p><span>Average Payment</span><span className="val">${growth_stats.avg_transaction_usd.toLocaleString()}</span></p>
          <p className="section-label">Monthly Volume</p>
          <VolumeChart data={growth_stats.monthly_volume} />
          <p className="section-label">Sources</p>
          <ul className="sources">
            {growth_stats.sources.map((source) => (
              <li key={source}>
                <a href={source} target="_blank" rel="noopener noreferrer">
                  {new URL(source).hostname.replace(/^www\./, "")}
                </a>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <SkeletonStatRow />
          <SkeletonStatRow valWidth="22%" />
          <SkeletonStatRow labelWidth="35%" valWidth="18%" />
          <SkeletonStatRow labelWidth="55%" valWidth="28%" />
        </>
      )}
    </div>
  );
}

export default GrowthStats;
