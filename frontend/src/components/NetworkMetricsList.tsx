import { useState, useEffect } from "react";
import type { NetworkMetrics } from "../types";
import { fetchNetworkMetrics } from "../api";

// ── Pulse Score Ring ──────────────────────────────────────────────────────────
function PulseRing({ score }: { score: number }) {
  const cx = 60, cy = 60, r = 44;
  const trackW = 10;
  const circumference = 2 * Math.PI * r;
  const ratio = Math.min(Math.max(score, 0), 100) / 100;
  const filled = ratio * circumference;
  const gap = circumference - filled;

  const arcColor =
    ratio < 0.4 ? "#aa0000" :
    ratio < 0.7 ? "#cc6600" :
                  "#f5c400";

  return (
    <svg viewBox="0 0 120 120" style={{ width: "100%", maxWidth: 130, display: "block", margin: "0 auto" }}>
      <defs>
        <filter id="pulse-glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="2.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Track ring */}
      <circle cx={cx} cy={cy} r={r}
        fill="none" stroke="#150505" strokeWidth={trackW} />

      {/* Progress arc — starts from 12 o'clock via rotate(-90) */}
      {ratio > 0 && (
        <circle cx={cx} cy={cy} r={r}
          fill="none"
          stroke={arcColor}
          strokeWidth={trackW - 2}
          strokeLinecap="round"
          strokeDasharray={`${filled.toFixed(2)} ${gap.toFixed(2)}`}
          transform={`rotate(-90 ${cx} ${cy})`}
          filter="url(#pulse-glow)"
          opacity={0.9}
        />
      )}

      {/* Score */}
      <g filter="url(#pulse-glow)" className="pulse-beat">
        <text x={cx} y={cy - 5}
          fill="var(--lightning)" fontSize="24" fontWeight="900"
          textAnchor="middle" dominantBaseline="middle">
          {Math.round(score)}
        </text>
      </g>
      <text x={cx} y={cy + 14}
        fill="var(--text-dim)" fontSize="7" textAnchor="middle"
        letterSpacing="0.12em">
        / 100
      </text>
    </svg>
  );
}

// ── Gini Lorenz Curve ─────────────────────────────────────────────────────────
// Approximation: L(x) = x^α  where α = (1+G)/(1−G).
// At G=0 → α=1 → L(x)=x (equality line).
// At G→1 → α→∞ → curve hugs the axes.
function LorenzCurve({ gini }: { gini: number }) {
  const M = 14;           // margin
  const S = 92;           // plot area side length
  const V = S + 2 * M;   // viewBox side = 120

  const alpha = (1 + gini) / Math.max(1 - gini, 0.001);

  // Origin = bottom-left in screen coords
  const ox = M, oy = M + S;       // (14, 106)
  const ex = M + S, ey = M;       // (106, 14) top-right

  // Generate Lorenz curve points
  const N = 80;
  const pts: { x: number; y: number }[] = [];
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    pts.push({
      x: M + S * t,
      y: M + S * (1 - Math.pow(t, alpha)),
    });
  }

  const lorenzD = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ");

  // Inequality fill: equality line → reversed Lorenz curve back to origin
  const fillD =
    `M ${ox} ${oy} L ${ex} ${ey} ` +
    pts.slice().reverse().map(p => `L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ") +
    " Z";

  return (
    <svg viewBox={`0 0 ${V} ${V}`} style={{ width: "100%", maxWidth: 130, display: "block", margin: "0 auto" }}>
      <defs>
        <filter id="lorenz-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Axes */}
      <line x1={ox} y1={oy} x2={ex} y2={oy} stroke="#1e0808" strokeWidth={0.8} />
      <line x1={ox} y1={oy} x2={ox} y2={ey} stroke="#1e0808" strokeWidth={0.8} />

      {/* Inequality fill */}
      <path d={fillD} fill="rgba(120, 20, 0, 0.18)" stroke="none" />

      {/* Equality line (dashed) */}
      <line x1={ox} y1={oy} x2={ex} y2={ey}
        stroke="#3a1010" strokeWidth={1.2} strokeDasharray="5 3" />

      {/* Lorenz curve */}
      <path d={lorenzD}
        fill="none" stroke="var(--amber)" strokeWidth={1.8}
        strokeLinecap="round" strokeLinejoin="round"
        filter="url(#lorenz-glow)" />

      {/* Axis labels */}
      <text x={ox + S / 2} y={oy + 11}
        fill="#4a2010" fontSize="6.5" textAnchor="middle">
        nodes →
      </text>
      <text
        x={ox - 10} y={oy - S / 2}
        fill="#4a2010" fontSize="6.5" textAnchor="middle"
        transform={`rotate(-90 ${ox - 10} ${oy - S / 2})`}>
        capacity →
      </text>
    </svg>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
function NetworkMetricsList() {
  const [network_metrics, setNetworkMetrics] = useState<NetworkMetrics | null>(null);

  useEffect(() => {
    fetchNetworkMetrics().then((data) => setNetworkMetrics(data));
  }, []);

  return (
    <div className="card">
      <h2>Network Metrics</h2>
      {network_metrics && (
        <>
          {/* ── Featured visuals ── */}
          <div className="nm-featured">
            <div className="nm-feature">
              <PulseRing score={network_metrics.pulse_score} />
              <div className="nm-feature-label">Pulse Score</div>
            </div>
            <div className="nm-feature">
              <LorenzCurve gini={network_metrics.gini_coefficient} />
              <div className="nm-feature-label">
                Gini&nbsp;
                <span className="nm-feature-val">{network_metrics.gini_coefficient.toFixed(3)}</span>
              </div>
            </div>
          </div>

          {/* ── Remaining stats ── */}
          <p><span>Top 10 Centralization</span><span className="val">{network_metrics.top10_centralization.toLocaleString()}</span></p>
          <p><span>Top 100 Centralization</span><span className="val">{network_metrics.top100_centralization.toLocaleString()}</span></p>
          <p><span>Median Fee Rate</span><span className="val">{network_metrics.median_fee_rate.toLocaleString()} ppm</span></p>
          <p><span>Median Node Degree</span><span className="val">{network_metrics.median_node_degree.toLocaleString()}</span></p>
          <p><span>Last Computed</span><span className="val">{network_metrics.last_computed}</span></p>
        </>
      )}
    </div>
  );
}

export default NetworkMetricsList;
