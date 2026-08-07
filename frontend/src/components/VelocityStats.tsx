import { useState, useEffect, useMemo } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { LiquidityVelocity, LightningStatsHistoryEntry, VelocityHistoryEntry } from "../types";
import { fetchVelocityStats, fetchLightningStatsHistory, fetchVelocityHistory } from "../api";
import { satsToBtc } from "../utils";
import InfoTooltip from "./InfoTooltip";
import { SkeletonCircle, SkeletonStatRow, SkeletonBlock } from "./Skeleton";

function VelocitySkeleton() {
  return (
    <div className="velocity-body">
      <SkeletonCircle size={130} />
      <SkeletonStatRow labelWidth="40%" valWidth="25%" />
      <SkeletonStatRow labelWidth="50%" valWidth="30%" />
      <SkeletonStatRow labelWidth="35%" valWidth="20%" />
    </div>
  );
}

const MAX_VEL = 5;

// Convert a "math angle" (degrees, 0=right/east, 90=up, 180=left/west) to an SVG point.
// SVG y increases downward, so y = cy - r*sin(angle).
function pt(cx: number, cy: number, angleDeg: number, radius: number) {
  const rad = angleDeg * (Math.PI / 180);
  return { x: cx + radius * Math.cos(rad), y: cy - radius * Math.sin(rad) };
}

// SVG arc segment going CW (sweep=1) through the top of the gauge.
// Works for arcs ≤ 180°.
function arcSeg(from: { x: number; y: number }, to: { x: number; y: number }, r: number) {
  return `M ${from.x.toFixed(2)} ${from.y.toFixed(2)} A ${r} ${r} 0 0 1 ${to.x.toFixed(2)} ${to.y.toFixed(2)}`;
}

function VelocityGauge({ velocity, onDone }: { velocity: number; onDone?: () => void }) {
  const cx = 100, cy = 98, r = 72;
  const trackW = 13;

  const ratio = Math.min(Math.max(velocity, 0), MAX_VEL) / MAX_VEL;

  // Animate from 0 → ratio on mount
  const [animRatio, setAnimRatio] = useState(0);
  useEffect(() => {
    const duration = 1400;
    const start = performance.now();
    function frame(now: number) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setAnimRatio(eased * ratio);
      if (t < 1) requestAnimationFrame(frame);
      else onDone?.();
    }
    const id = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(id);
  }, [ratio]);

  // Gauge spans from 180° (9-o'clock / left) → 0° (3-o'clock / right), CW through top.
  const needleAngle = 180 - animRatio * 180;

  const startPt = pt(cx, cy, 180, r);  // left  (28, 98)
  const endPt   = pt(cx, cy, 0,   r);  // right (172, 98)

  // Zone boundary angles (low / mid / high)
  const z1Angle = 180 - 0.33 * 180; // ~120°
  const z2Angle = 180 - 0.66 * 180; // ~60°
  const z1Pt = pt(cx, cy, z1Angle, r);
  const z2Pt = pt(cx, cy, z2Angle, r);

  // Active fill endpoint on the track radius
  const fillPt = pt(cx, cy, needleAngle, r);

  // Needle tip (slightly inside the track so it points to the arc)
  const needleTip = pt(cx, cy, needleAngle, r - 6);

  // Active fill color based on zone
  const fillColor =
    animRatio < 0.33 ? "#aa0000" :
    animRatio < 0.66 ? "#cc6600" :
                       "#f5c400";

  // Tick marks and labels at each integer velocity step
  const ticks = Array.from({ length: MAX_VEL + 1 }, (_, i) => i / MAX_VEL);

  return (
    <svg viewBox="0 0 200 118" style={{ width: "100%", maxWidth: 300, display: "block", margin: "0 auto" }}>
      <defs>
        <filter id="vel-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="needle-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="1.8" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* ── Track background ── */}
      <path
        d={`M ${startPt.x} ${startPt.y} A ${r} ${r} 0 0 1 ${endPt.x} ${endPt.y}`}
        fill="none" stroke="#150505" strokeWidth={trackW} strokeLinecap="round"
      />

      {/* ── Zone tinting ── */}
      <path d={arcSeg(startPt, z1Pt, r)}
        fill="none" stroke="#3a0000" strokeWidth={trackW} strokeLinecap="butt" />
      <path d={arcSeg(z1Pt,   z2Pt, r)}
        fill="none" stroke="#3a1e00" strokeWidth={trackW} strokeLinecap="butt" />
      <path d={arcSeg(z2Pt,   endPt, r)}
        fill="none" stroke="#3a3000" strokeWidth={trackW} strokeLinecap="butt" />

      {/* ── Active fill (glow arc from start to needle) ── */}
      {animRatio > 0.005 && (
        <path
          d={`M ${startPt.x.toFixed(2)} ${startPt.y.toFixed(2)} A ${r} ${r} 0 0 1 ${fillPt.x.toFixed(2)} ${fillPt.y.toFixed(2)}`}
          fill="none" stroke={fillColor} strokeWidth={trackW - 3}
          strokeLinecap="round" filter="url(#vel-glow)" opacity={0.9}
        />
      )}

      {/* ── Tick marks ── */}
      {ticks.map((t) => {
        const angle = 180 - t * 180;
        const inner = pt(cx, cy, angle, r - trackW / 2 - 3);
        const outer = pt(cx, cy, angle, r + trackW / 2 + 3);
        return (
          <line key={t}
            x1={inner.x.toFixed(2)} y1={inner.y.toFixed(2)}
            x2={outer.x.toFixed(2)} y2={outer.y.toFixed(2)}
            stroke="#3a1010" strokeWidth={t === 0 || t === 1 ? 2 : 1.2}
          />
        );
      })}

      {/* ── Tick labels ── */}
      {ticks.map((t) => {
        const angle = 180 - t * 180;
        const labelPt = pt(cx, cy, angle, r + trackW / 2 + 13);
        return (
          <text key={t}
            x={labelPt.x.toFixed(2)} y={labelPt.y.toFixed(2)}
            fill="#5a2810" fontSize="7.5" textAnchor="middle" dominantBaseline="middle"
          >
            {Math.round(t * MAX_VEL)}
          </text>
        );
      })}

      {/* ── Needle ── */}
      <line
        x1={cx} y1={cy}
        x2={needleTip.x.toFixed(2)} y2={needleTip.y.toFixed(2)}
        stroke="var(--lightning)" strokeWidth={2.2} strokeLinecap="round"
        filter="url(#needle-glow)"
      />

      {/* ── Pivot ── */}
      <circle cx={cx} cy={cy} r={5.5} fill="var(--lightning)" filter="url(#needle-glow)" />
      <circle cx={cx} cy={cy} r={3}   fill="var(--bg-card)" />
    </svg>
  );
}

const SATS_PER_BTC = 100_000_000;

type TrendPoint = { t: number; v: number; ma: number };

const fmtDate = (t: number) => new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });

// One value per UTC day (last snapshot wins) — backend restarts can persist several per day
function dailyValues(entries: { recorded_at: string; value: number }[]): { t: number; v: number }[] {
  const byDay = new Map<string, { t: number; v: number }>();
  for (const e of entries) {
    const date = new Date(e.recorded_at);
    if (e.value > 0) {
      byDay.set(date.toISOString().slice(0, 10), { t: date.getTime(), v: e.value });
    }
  }
  return [...byDay.values()].sort((a, b) => a.t - b.t);
}

// Attach a 7-day trailing moving average, which the trend line is drawn from
function movingAverage(daily: { t: number; v: number }[]): TrendPoint[] {
  return daily.map((p, i) => {
    const from = Math.max(0, i - 6);
    let sum = 0;
    for (let j = from; j <= i; j++) sum += daily[j].v;
    return { ...p, ma: sum / (i - from + 1) };
  });
}

// Round-number y-axis ticks within [vMin, vMax], aiming for ~4 intervals
function niceTicks(vMin: number, vMax: number): number[] {
  const span = vMax - vMin;
  const mag = Math.pow(10, Math.floor(Math.log10(span / 4)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= 4) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = Math.ceil(vMin / step) * step; v <= vMax && ticks.length < 10; v += step) ticks.push(v);
  return ticks;
}

// Hand-rolled SVG trend chart, shared by the capacity and velocity series.
// The source data jumps around day-to-day (stale/cached upstream values), so the
// line is a 7-day moving average with the y range fitted tightly to it.
// Hovering snaps to the nearest day and reads the trend value at that point.
function TrendChart({ pts, hovered, onHover, formatTick }: {
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

function TrendView({ history, velHistory }: {
  history: LightningStatsHistoryEntry[] | null;
  velHistory: VelocityHistoryEntry[] | null;
}) {
  const [hovered, setHovered] = useState<TrendPoint | null>(null);
  const [series, setSeries] = useState<"capacity" | "velocity">("capacity");

  const capPts = useMemo(
    () => movingAverage(dailyValues((history ?? []).map((d) => ({
      recorded_at: d.recorded_at,
      value: d.total_capacity / SATS_PER_BTC,
    })))),
    [history]
  );
  const velPts = useMemo(
    () => movingAverage(dailyValues((velHistory ?? []).map((d) => ({
      recorded_at: d.recorded_at,
      value: d.velocity,
    })))),
    [velHistory]
  );

  if (!history) {
    return (
      <div className="velocity-body">
        <SkeletonBlock height={150} />
      </div>
    );
  }
  if (capPts.length < 2) {
    return (
      <div className="velocity-body">
        <p className="velocity-trend-empty">
          Collecting daily snapshots — the trend chart appears once a few days of data exist.
        </p>
      </div>
    );
  }

  const hasVelocity = velPts.length >= 2;
  const isCap = series === "capacity" || !hasVelocity;
  const pts = isCap ? capPts : velPts;

  const first = pts[0];
  const latest = pts[pts.length - 1];
  const deltaPct = ((latest.ma - first.ma) / first.ma) * 100;
  const spanDays = Math.max(1, Math.round((latest.t - first.t) / 86_400_000));

  const formatValue = isCap
    ? (v: number) => satsToBtc(Math.round(v * SATS_PER_BTC))
    : (v: number) => `${v.toFixed(2)} turns/mo`;
  const formatTick = isCap
    ? (v: number) => Math.round(v).toLocaleString()
    : (v: number) => v.toFixed(2).replace(/\.?0+$/, "");
  const caption = isCap
    ? "Total network capacity · 7-day moving average"
    : "Monthly volume ÷ capacity · 7-day moving average";

  function pickSeries(s: "capacity" | "velocity") {
    setSeries(s);
    setHovered(null);
  }

  return (
    <div className="velocity-body">
      <div className="velocity-trend-header">
        <span className="vt-current">{formatValue(hovered ? hovered.ma : latest.ma)}</span>
        {hovered ? (
          <span className="vt-delta">{fmtDate(hovered.t)}</span>
        ) : (
          <span className={`vt-delta${deltaPct >= 0 ? " vt-delta--up" : " vt-delta--down"}`}>
            {deltaPct >= 0 ? "+" : ""}{deltaPct.toFixed(1)}% · {spanDays}d
          </span>
        )}
      </div>
      {hasVelocity && (
        <div className="velocity-series-row">
          <span className="velocity-toggle">
            <button
              className={`vt-btn${isCap ? " vt-btn--active" : ""}`}
              onClick={() => pickSeries("capacity")}
            >
              Capacity
            </button>
            <button
              className={`vt-btn${!isCap ? " vt-btn--active" : ""}`}
              onClick={() => pickSeries("velocity")}
            >
              Velocity
            </button>
          </span>
        </div>
      )}
      <TrendChart pts={pts} hovered={hovered} onHover={setHovered} formatTick={formatTick} />
      <span className="velocity-trend-caption">{caption}</span>
    </div>
  );
}

function VelocityStats({ refreshKey }: { refreshKey?: number }) {
  const [velocity_stats, setVelocityStats] = useState<LiquidityVelocity | null>(null);
  const [flash, setFlash] = useState(false);
  const [view, setView] = useState<"gauge" | "trend">("gauge");
  const [history, setHistory] = useState<LightningStatsHistoryEntry[] | null>(null);
  const [velHistory, setVelHistory] = useState<VelocityHistoryEntry[] | null>(null);
  const [historyAvailable, setHistoryAvailable] = useState(true);

  useEffect(() => {
    fetchVelocityStats().then((data) => setVelocityStats(data));
  }, [refreshKey]);

  // History only changes with the 24h snapshot cycle — fetch once on mount, not on every refresh.
  useEffect(() => {
    fetchLightningStatsHistory(90)
      .then((data) => setHistory(data))
      .catch(() => {
        // MongoDB not configured (503) — fall back to gauge-only, no toggle
        setHistoryAvailable(false);
        setView("gauge");
      });
    fetchVelocityHistory(90)
      .then((data) => setVelHistory(data))
      .catch(() => setVelHistory([]));  // derived series unavailable — hide the Velocity option
  }, []);

  function handleDone() {
    setFlash(true);
  }

  return (
    <div className={`card velocity-card${flash ? " card--flash" : ""}`}>
      <h2>
        <span>
          Liquidity Velocity
          <InfoTooltip>
            <span className="info-tooltip-title">What is Liquidity Velocity?</span>
            <p className="info-tooltip-body">
              Velocity measures <strong>how efficiently capital is being used</strong> — not just how much exists.
              A high-capacity network with low velocity is like cash sitting idle in a vault.
              <span className="info-tooltip-formula">Velocity = Monthly Volume ÷ Total Capacity</span>
              A score of <strong>1.0</strong> means the entire network capacity is routed once per month.
              At <strong>3.12</strong>, the Lightning Network is turning over its full capacity more than
              3× every month — a strong indicator of active, efficient utilization.
              <span className="info-tooltip-note">
                ⚡ Capacity is sourced live from the Lightning Network. Monthly volume uses published
                estimates from River &amp; Breez — exact figures are unknowable since Lightning
                payments are private by design. The <strong>Trend</strong> view charts total network
                capacity as a 7-day moving average of daily snapshots — hover to read the trend at any day.
                The Velocity series derives historical turns from daily capacity and historical BTC
                prices, with the latest volume estimate held constant.
              </span>
            </p>
          </InfoTooltip>
        </span>
        {historyAvailable && (
          <span className="velocity-toggle">
            <button
              className={`vt-btn${view === "gauge" ? " vt-btn--active" : ""}`}
              onClick={() => setView("gauge")}
            >
              Gauge
            </button>
            <button
              className={`vt-btn${view === "trend" ? " vt-btn--active" : ""}`}
              onClick={() => setView("trend")}
            >
              Trend
            </button>
          </span>
        )}
      </h2>
      {view === "trend" ? (
        <TrendView history={history} velHistory={velHistory} />
      ) : velocity_stats ? (
        <div className="velocity-body">
          <VelocityGauge velocity={velocity_stats.velocity} onDone={handleDone} />

          <div className="velocity-readout">
            <span className="velocity-number">{velocity_stats.velocity.toFixed(2)}</span>
            <span className="velocity-unit">turns / month</span>
          </div>

          <div className="velocity-grid">
            <div className="vg-item">
              <span className="vg-label">Monthly Vol.</span>
              <span className="vg-val">${velocity_stats.monthly_volume_usd.toLocaleString()}</span>
            </div>
            <div className="vg-item">
              <span className="vg-label">Capacity (USD)</span>
              <span className="vg-val">${velocity_stats.capacity_usd.toLocaleString()}</span>
            </div>
            <div className="vg-item">
              <span className="vg-label">Capacity</span>
              <span className="vg-val">{satsToBtc(velocity_stats.capacity_sats)}</span>
            </div>
          </div>
        </div>
      ) : (
        <VelocitySkeleton />
      )}
    </div>
  );
}

export default VelocityStats;
