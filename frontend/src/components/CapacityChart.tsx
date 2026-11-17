import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { niceTicks } from "../utils";

// The report card's capacity chart: raw daily readings on a true time axis, with both
// axes labelled and the comparison the analysis text makes drawn on it.
//
// Not TrendChart. That one plots a 7-day moving average (the reading *is* the story
// here, so smoothing would blur it) and formats its dates through the viewer's locale
// and zone, which this card avoids everywhere: these are UTC calendar days.
//
// Laid out in real pixels from the measured width rather than a scaled viewBox, so the
// axis text stays one size however narrow the card gets.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_MS = 86_400_000;

// Readings further apart than this are joined by a dashed line rather than a solid
// one: the line crosses a stretch we have no readings for, and should not look measured.
const GAP_DAYS = 3;

const MIN_H = 190; // never drawn shorter than this, whatever the column gives it
const PAD = { left: 58, right: 12, top: 10, bottom: 40 };

// UTC midnight of an ISO date, from its parts.
const toMs = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
};

const fmtMs = (t: number) => {
  const dt = new Date(t);
  return `${dt.getUTCDate()} ${MONTHS[dt.getUTCMonth()]}`;
};

const fmtBtc = (v: number) => Math.round(v).toLocaleString();

export function CapacityChart({
  dates,
  values,
  recentDays,
  longDays,
}: {
  dates: string[];
  values: number[];
  recentDays: number | null; // where the "recent" leg of the analysis begins
  longDays: number; // the span of the long-run pace line
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [hover, setHover] = useState<number | null>(null);

  // The plot is drawn to fill the box its column gives it, width and height.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const read = () => setSize({ width: Math.floor(el.clientWidth), height: Math.floor(el.clientHeight) });
    read();
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  const { width } = size;
  const H = Math.max(size.height, MIN_H);

  if (values.length < 2 || dates.length !== values.length) return null;

  const n = values.length;
  const ts = dates.map(toMs);
  const t0 = ts[0];
  const t1 = ts[n - 1];
  const plotW = Math.max(width - PAD.left - PAD.right, 1);
  const plotH = H - PAD.top - PAD.bottom;
  const baseY = PAD.top + plotH;

  // Fit the y range to the readings, with room so the line never touches the frame.
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = (hi - lo) * 0.1 || hi * 0.02 || 1;
  const vMin = lo - pad;
  const vMax = hi + pad;
  const yTicks = niceTicks(vMin, vMax);

  const x = (t: number) => PAD.left + ((t - t0) / Math.max(t1 - t0, 1)) * plotW;
  const y = (v: number) => PAD.top + (1 - (v - vMin) / (vMax - vMin)) * plotH;

  // Four evenly spaced dates, snapped to whole days, first and last pinned to the ends.
  const xTicks = [0, 1, 2, 3].map((k) => Math.round((t0 + ((t1 - t0) * k) / 3) / DAY_MS) * DAY_MS);

  // Solid where readings are consecutive, dashed across a gap.
  let solid = "";
  let dashed = "";
  for (let i = 1; i < n; i++) {
    const seg = `M ${x(ts[i - 1]).toFixed(1)} ${y(values[i - 1]).toFixed(1)} L ${x(ts[i]).toFixed(1)} ${y(values[i]).toFixed(1)} `;
    if ((ts[i] - ts[i - 1]) / DAY_MS > GAP_DAYS) dashed += seg;
    else solid += seg;
  }

  const recentT = recentDays !== null ? t1 - recentDays * DAY_MS : null;
  const showRecent = recentT !== null && recentT > t0;

  function handleMove(e: ReactPointerEvent<SVGSVGElement>) {
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
    let best = 0;
    let bestDist = Infinity;
    for (let i = 0; i < n; i++) {
      const d = Math.abs(x(ts[i]) - px);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    }
    setHover(best);
  }

  const label = `Network capacity from ${fmtMs(t0)} to ${fmtMs(t1)}, ${fmtBtc(values[0])} to ${fmtBtc(values[n - 1])} BTC`;
  const text = { fill: "var(--text-dim)", fontSize: 10 } as const;

  return (
    <div className="rc-chart">
      <div className="rc-chart-head">
        <span className="rc-chart-legend">
          <span><i className="rc-key rc-key--line" />Capacity</span>
          <span><i className="rc-key rc-key--pace" />{longDays}-day pace</span>
          {showRecent && <span><i className="rc-key rc-key--mark" />{recentDays} days ago</span>}
        </span>
        <span className="rc-chart-readout">
          {hover !== null ? `${fmtMs(ts[hover])} · ${fmtBtc(values[hover])} BTC` : "Daily readings · UTC"}
        </span>
      </div>

      <div ref={wrapRef} className="rc-chart-plot">
        {width > 0 && (
          <svg
            width={width}
            height={H}
            role="img"
            aria-label={label}
            style={{ position: "absolute", left: 0, top: 0, touchAction: "pan-y", cursor: "crosshair" }}
            onPointerMove={handleMove}
            onPointerLeave={() => setHover(null)}
          >
            {/* Gridlines and y labels at round numbers */}
            {yTicks.map((tv) => (
              <g key={tv}>
                <line x1={PAD.left} x2={PAD.left + plotW} y1={y(tv)} y2={y(tv)}
                  stroke="var(--separator)" strokeWidth={1} strokeDasharray="3 4" />
                <text x={PAD.left - 7} y={y(tv)} textAnchor="end" dominantBaseline="middle" {...text}>
                  {fmtBtc(tv)}
                </text>
              </g>
            ))}

            {/* The frame, so the plot reads as a bounded area */}
            <rect x={PAD.left} y={PAD.top} width={plotW} height={plotH}
              fill="none" stroke="var(--separator)" strokeWidth={1} />

            {/* The 90-day pace: the straight line from the first reading to the last */}
            <line x1={x(t0)} y1={y(values[0])} x2={x(t1)} y2={y(values[n - 1])}
              stroke="var(--text-dim)" strokeWidth={1.2} strokeDasharray="5 4" opacity={0.7} />

            {/* Where the recent leg starts */}
            {showRecent && (
              <line x1={x(recentT as number)} x2={x(recentT as number)} y1={PAD.top} y2={baseY}
                stroke="var(--amber)" strokeWidth={1.2} strokeDasharray="1 3" strokeLinecap="round" />
            )}

            {/* Capacity: solid between consecutive readings, dashed across a gap */}
            {dashed && (
              <path d={dashed} fill="none" stroke="var(--lightning)" strokeWidth={1.4}
                strokeDasharray="3 3" strokeLinecap="round" opacity={0.75} />
            )}
            <path d={solid} fill="none" stroke="var(--lightning)" strokeWidth={1.8}
              strokeLinecap="round" strokeLinejoin="round" />

            {/* Hovered reading */}
            {hover !== null && (
              <g>
                <line x1={x(ts[hover])} x2={x(ts[hover])} y1={PAD.top} y2={baseY}
                  stroke="var(--text-dim)" strokeWidth={1} opacity={0.5} />
                <circle cx={x(ts[hover])} cy={y(values[hover])} r={3.4}
                  fill="var(--lightning)" stroke="var(--bg-card)" strokeWidth={1.5} />
              </g>
            )}

            {/* X axis: tick marks, dates, title */}
            {xTicks.map((tt, k) => (
              <g key={tt}>
                <line x1={x(tt)} x2={x(tt)} y1={baseY} y2={baseY + 4} stroke="var(--separator)" strokeWidth={1} />
                <text x={x(tt)} y={baseY + 16}
                  textAnchor={k === 0 ? "start" : k === 3 ? "end" : "middle"} {...text}>
                  {fmtMs(tt)}
                </text>
              </g>
            ))}
            <text x={PAD.left + plotW / 2} y={H - 4} textAnchor="middle" {...text} opacity={0.7}>
              UTC date
            </text>

            {/* Y axis title */}
            <text transform={`translate(12 ${PAD.top + plotH / 2}) rotate(-90)`}
              textAnchor="middle" {...text} opacity={0.7}>
              BTC
            </text>
          </svg>
        )}
      </div>
    </div>
  );
}
