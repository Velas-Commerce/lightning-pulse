import { useState, useEffect } from "react";
import type { LiquidityVelocity } from "../types";
import { fetchVelocityStats } from "../api";
import { satsToBtc } from "../utils";
import InfoTooltip from "./InfoTooltip";
import { SkeletonCircle, SkeletonStatRow } from "./Skeleton";

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

function VelocityStats({ refreshKey }: { refreshKey?: number }) {
  const [velocity_stats, setVelocityStats] = useState<LiquidityVelocity | null>(null);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    fetchVelocityStats().then((data) => setVelocityStats(data));
  }, [refreshKey]);

  function handleDone() {
    setFlash(true);
  }

  return (
    <div className={`card velocity-card${flash ? " card--flash" : ""}`}>
      <h2>
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
              payments are private by design.
            </span>
          </p>
        </InfoTooltip>
      </h2>
      {velocity_stats ? (
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
