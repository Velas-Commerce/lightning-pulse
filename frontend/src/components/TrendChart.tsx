import { useState, useEffect } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { fmtDate } from "../utils";
import type { TrendPoint } from "../utils";

// Round-number y-axis ticks within [vMin, vMax], aiming for ~4 intervals
function niceTicks(vMin: number, vMax: number): number[] {
  const span = vMax - vMin;
  const mag = Math.pow(10, Math.floor(Math.log10(span / 4)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= 4) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = Math.ceil(vMin / step) * step; v <= vMax && ticks.length < 10; v += step) ticks.push(v);
  return ticks;
}

// Hand-rolled SVG trend chart, shared by all history series (capacity, velocity,
// network metrics). The source data jumps around day-to-day (stale/cached upstream
// values), so the line is a 7-day moving average with the y range fitted tightly to it.
// Hovering snaps to the nearest day and reads the trend value at that point.
export function TrendChart({ pts, hovered, onHover, formatTick }: {
  pts: TrendPoint[];
  hovered: TrendPoint | null;
  onHover: (p: TrendPoint | null) => void;
  formatTick: (v: number) => string;
}) {
  const W = 200, H = 110;
  const padL = 22, padR = 6, padT = 8, padB = 14;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const baseY = padT + plotH;

  const tMin = pts[0].t;
  const tMax = pts[pts.length - 1].t;
  const maMin = Math.min(...pts.map((p) => p.ma));
  const maMax = Math.max(...pts.map((p) => p.ma));
  // Fit the y range tightly to the trend line (flat data still renders)
  const span = maMax - maMin || maMax * 0.02 || 1;
  const vMin = maMin - span * 0.1;
  const vMax = maMax + span * 0.1;

  const x = (t: number) => padL + ((t - tMin) / Math.max(tMax - tMin, 1)) * plotW;
  const y = (v: number) => padT + (1 - (v - vMin) / (vMax - vMin)) * plotH;

  // Animate the line drawing from left → right on mount (same trick as the Lorenz curve)
  const [animOffset, setAnimOffset] = useState(1);
  const [fillOpacity, setFillOpacity] = useState(0);
  useEffect(() => {
    const duration = 1400;
    const start = performance.now();
    function frame(now: number) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setAnimOffset(1 - eased);
      setFillOpacity(eased);
      if (t < 1) requestAnimationFrame(frame);
    }
    const id = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(id);
  }, [pts]);

  const lineD = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.t).toFixed(2)} ${y(p.ma).toFixed(2)}`).join(" ");
  const areaD = `${lineD} L ${x(tMax).toFixed(2)} ${baseY} L ${x(tMin).toFixed(2)} ${baseY} Z`;

  function handlePointerMove(e: ReactPointerEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * W;
    let best = pts[0];
    let bestDist = Infinity;
    for (const p of pts) {
      const d = Math.abs(x(p.t) - svgX);
      if (d < bestDist) { bestDist = d; best = p; }
    }
    onHover(best);
  }

  const lastPt = pts[pts.length - 1];
  const ticks = niceTicks(vMin, vMax);

  return (
    <svg viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", display: "block", cursor: "crosshair", touchAction: "none" }}
      onPointerMove={handlePointerMove}
      onPointerLeave={() => onHover(null)}
    >
      <defs>
        <filter id="cap-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1.8" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id="cap-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f5c400" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#f5c400" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Y axis: gridlines + labels at round-number ticks */}
      {ticks.map((tv) => (
        <g key={tv}>
          <line x1={padL} y1={y(tv)} x2={W - padR} y2={y(tv)}
            stroke="#1e0808" strokeWidth={0.6} strokeDasharray="3 3" />
          <text x={padL - 3} y={y(tv)} textAnchor="end" dominantBaseline="middle"
            fill="#4a2010" fontSize="6.5">{formatTick(tv)}</text>
        </g>
      ))}

      {/* Baseline */}
      <line x1={padL} y1={baseY} x2={W - padR} y2={baseY} stroke="#1e0808" strokeWidth={0.8} />

      {/* Area fill under the line */}
      <path d={areaD} fill="url(#cap-fill)" opacity={fillOpacity} />

      {/* Trend line — pathLength="1" normalises length so dashoffset 1→0 draws the line */}
      <path d={lineD}
        fill="none" stroke="var(--lightning)" strokeWidth={1.8}
        strokeLinecap="round" strokeLinejoin="round"
        pathLength={1} strokeDasharray={1} strokeDashoffset={animOffset}
        filter="url(#cap-glow)" />

      {/* Hovered day: crosshair + dot on the line; otherwise endpoint marker */}
      {hovered ? (
        <g>
          <line x1={x(hovered.t)} y1={padT} x2={x(hovered.t)} y2={baseY}
            stroke="#3a1010" strokeWidth={0.8} strokeDasharray="2 2" />
          <circle cx={x(hovered.t)} cy={y(hovered.ma)} r={2.6}
            fill="var(--lightning)" filter="url(#cap-glow)" />
        </g>
      ) : (
        <circle cx={x(lastPt.t)} cy={y(lastPt.ma)} r={2.2}
          fill="var(--lightning)" filter="url(#cap-glow)" opacity={1 - animOffset} />
      )}

      {/* X range (dates) */}
      <text x={padL} y={H - 3} fill="#4a2010" fontSize="6.5">{fmtDate(tMin)}</text>
      <text x={W - padR} y={H - 3} fill="#4a2010" fontSize="6.5" textAnchor="end">{fmtDate(tMax)}</text>
    </svg>
  );
}
