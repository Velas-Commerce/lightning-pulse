import { useState, useEffect, useMemo } from "react";
import type { NetworkMetrics, NetworkMetricsHistoryEntry } from "../types";
import { fetchNetworkMetrics, fetchNetworkMetricsHistory } from "../api";
import { dailyValues, movingAverage, fmtDate } from "../utils";
import type { TrendPoint } from "../utils";
import { TrendChart } from "./TrendChart";
import InfoTooltip from "./InfoTooltip";
import { SkeletonCircle, SkeletonStatRow, SkeletonBlock } from "./Skeleton";

function NetworkMetricsSkeleton() {
  return (
    <>
      <div className="nm-featured">
        <div className="nm-feature"><SkeletonCircle size={120} /></div>
        <div className="nm-feature"><SkeletonCircle size={120} /></div>
      </div>
      <SkeletonStatRow />
      <SkeletonStatRow valWidth="20%" />
      <SkeletonStatRow labelWidth="40%" valWidth="25%" />
      <SkeletonStatRow labelWidth="45%" valWidth="22%" />
      <SkeletonStatRow labelWidth="38%" valWidth="35%" />
    </>
  );
}

// ── Replicate backend component scoring ───────────────────────────────────────
function calcComponents(gini: number, top10: number, feeRate: number) {
  const equity = Math.max(0, Math.min(100, (0.95 - gini) / 0.35 * 100));
  const decentralization = Math.max(0, Math.min(100, (0.70 - top10) / 0.50 * 100));
  let fee = 0;
  if (feeRate <= 0) fee = 0;
  else if (feeRate < 500) fee = feeRate / 500 * 60;
  else if (feeRate <= 5000) fee = 100;
  else if (feeRate <= 20000) fee = Math.max(0, 100 - (feeRate - 5000) / 150);
  return { equity, decentralization, fee };
}

// ── Pulse Score Ring ──────────────────────────────────────────────────────────
function PulseRing({ score, gini, top10, feeRate }: {
  score: number; gini: number; top10: number; feeRate: number;
}) {
  const cx = 60, cy = 60, r = 44;
  const trackW = 10;
  const circumference = 2 * Math.PI * r;
  const ratio = Math.min(Math.max(score, 0), 100) / 100;

  // Animate from 0 → ratio on mount
  const [animRatio, setAnimRatio] = useState(0);
  useEffect(() => {
    const duration = 1200;
    const start = performance.now();
    function frame(now: number) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setAnimRatio(eased * ratio);
      if (t < 1) requestAnimationFrame(frame);
    }
    const id = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(id);
  }, [ratio]);

  const filled = animRatio * circumference;
  const gap = circumference - filled;

  const arcColor =
    animRatio < 0.4 ? "#aa0000" :
    animRatio < 0.7 ? "#cc6600" :
                      "#f5c400";

  const [hovered, setHovered] = useState(false);
  const { equity, decentralization, fee } = calcComponents(gini, top10, feeRate);

  return (
    <svg
      viewBox="0 0 120 120"
      style={{ width: "100%", maxWidth: 130, display: "block", margin: "0 auto", cursor: "default" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
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
          opacity={hovered ? 0.35 : 0.9}
          style={{ transition: "opacity 0.2s" }}
        />
      )}

      {/* Default: score */}
      {!hovered && (
        <g filter="url(#pulse-glow)" className="pulse-beat">
          <text x={cx} y={cy - 5}
            fill="var(--lightning)" fontSize="24" fontWeight="900"
            textAnchor="middle" dominantBaseline="middle">
            {Math.round(score)}
          </text>
        </g>
      )}
      {!hovered && (
        <text x={cx} y={cy + 14}
          fill="var(--text-dim)" fontSize="7" textAnchor="middle"
          letterSpacing="0.12em">
          / 100
        </text>
      )}

      {/* Hover: component breakdown */}
      {hovered && (
        <g>
          <text x={cx} y={22} textAnchor="middle" fill="#a08868" fontSize="13" letterSpacing="0.08em">EQUITY</text>
          <text x={cx} y={40} textAnchor="middle" fill="var(--lightning)" fontSize="26" fontWeight="700">{equity.toFixed(0)}</text>

          <text x={cx} y={62} textAnchor="middle" fill="#a08868" fontSize="13" letterSpacing="0.08em">DECENT.</text>
          <text x={cx} y={80} textAnchor="middle" fill="var(--lightning)" fontSize="26" fontWeight="700">{decentralization.toFixed(0)}</text>

          <text x={cx} y={102} textAnchor="middle" fill="#a08868" fontSize="13" letterSpacing="0.08em">FEE HEALTH</text>
          <text x={cx} y={118} textAnchor="middle" fill="var(--lightning)" fontSize="26" fontWeight="700">{fee.toFixed(0)}</text>
        </g>
      )}
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

  // Animate the curve drawing from left → right on mount
  const [animOffset, setAnimOffset] = useState(1);
  const [fillOpacity, setFillOpacity] = useState(0);
  useEffect(() => {
    const duration = 1600;
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
  }, [gini]);

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
      <path d={fillD} fill="rgba(120, 20, 0, 0.18)" stroke="none" opacity={fillOpacity} />

      {/* Equality line (dashed) */}
      <line x1={ox} y1={oy} x2={ex} y2={ey}
        stroke="#3a1010" strokeWidth={1.2} strokeDasharray="5 3" />

      {/* Lorenz curve — pathLength="1" normalises length so dashoffset 0→1 draws the line */}
      <path d={lorenzD}
        fill="none" stroke="var(--amber)" strokeWidth={1.8}
        strokeLinecap="round" strokeLinejoin="round"
        pathLength={1} strokeDasharray={1} strokeDashoffset={animOffset}
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

// ── Trend view ────────────────────────────────────────────────────────────────
// Trackable series from the daily network_metrics snapshots. Pulse is the headline
// health number; Gini / Top 10 tell the (de)centralization story; fee rate shows
// the routing market direction. Deltas are absolute (points), not percent change.
type MetricsSeriesKey = "pulse" | "gini" | "top10" | "fee";

const METRICS_SERIES: {
  key: MetricsSeriesKey;
  label: string;
  value: (d: NetworkMetricsHistoryEntry) => number;
  format: (v: number) => string;
  formatDelta: (v: number) => string;
  formatTick: (v: number) => string;
  caption: string;
}[] = [
  {
    key: "pulse",
    label: "Pulse",
    value: (d) => d.pulse_score,
    format: (v) => `${Math.round(v)} / 100`,
    formatDelta: (v) => `${Math.round(v)} pts`,
    formatTick: (v) => `${Math.round(v)}`,
    caption: "Pulse score · 7-day moving average",
  },
  {
    key: "gini",
    label: "Gini",
    value: (d) => d.gini_coefficient,
    format: (v) => v.toFixed(3),
    formatDelta: (v) => v.toFixed(3),
    formatTick: (v) => v.toFixed(2),
    caption: "Gini coefficient (capacity equality) · 7-day moving average",
  },
  {
    key: "top10",
    label: "Top 10",
    value: (d) => d.top10_centralization * 100,
    format: (v) => `${v.toFixed(1)}%`,
    formatDelta: (v) => `${v.toFixed(1)}%`,
    formatTick: (v) => `${Math.round(v)}%`,
    caption: "Share of capacity held by the top 10 nodes · 7-day moving average",
  },
  {
    key: "fee",
    label: "Fee Rate",
    value: (d) => d.median_fee_rate,
    format: (v) => `${Math.round(v)} ppm`,
    formatDelta: (v) => `${Math.round(v)} ppm`,
    formatTick: (v) => `${Math.round(v)}`,
    caption: "Median routing fee rate · 7-day moving average",
  },
];

function MetricsTrendView({ history }: { history: NetworkMetricsHistoryEntry[] | null }) {
  const [hovered, setHovered] = useState<TrendPoint | null>(null);
  const [seriesKey, setSeriesKey] = useState<MetricsSeriesKey>("pulse");

  const ptsBySeries = useMemo(() => {
    const out = {} as Record<MetricsSeriesKey, TrendPoint[]>;
    for (const s of METRICS_SERIES) {
      out[s.key] = movingAverage(dailyValues((history ?? []).map((d) => ({
        recorded_at: d.recorded_at,
        value: s.value(d),
      }))));
    }
    return out;
  }, [history]);

  if (!history) {
    return (
      <div className="velocity-body">
        <SkeletonBlock height={150} />
      </div>
    );
  }

  const series = METRICS_SERIES.find((s) => s.key === seriesKey) ?? METRICS_SERIES[0];
  const pts = ptsBySeries[series.key];

  if (pts.length < 2) {
    return (
      <div className="velocity-body">
        <p className="velocity-trend-empty">
          Collecting daily snapshots — the trend chart appears once a few days of data exist.
        </p>
      </div>
    );
  }

  const first = pts[0];
  const latest = pts[pts.length - 1];
  const delta = latest.ma - first.ma;
  const spanDays = Math.max(1, Math.round((latest.t - first.t) / 86_400_000));

  function pickSeries(key: MetricsSeriesKey) {
    setSeriesKey(key);
    setHovered(null);
  }

  return (
    <div className="velocity-body">
      <div className="velocity-trend-header">
        <span className="vt-current">{series.format(hovered ? hovered.ma : latest.ma)}</span>
        {hovered ? (
          <span className="vt-delta">{fmtDate(hovered.t)}</span>
        ) : (
          <span className={`vt-delta${delta >= 0 ? " vt-delta--up" : " vt-delta--down"}`}>
            {delta >= 0 ? "+" : "-"}{series.formatDelta(Math.abs(delta))} · {spanDays}d
          </span>
        )}
      </div>
      <div className="velocity-series-row">
        <span className="velocity-toggle">
          {METRICS_SERIES.map((s) => (
            <button
              key={s.key}
              className={`vt-btn${s.key === series.key ? " vt-btn--active" : ""}`}
              onClick={() => pickSeries(s.key)}
            >
              {s.label}
            </button>
          ))}
        </span>
      </div>
      <TrendChart pts={pts} hovered={hovered} onHover={setHovered} formatTick={series.formatTick} />
      <span className="velocity-trend-caption">{series.caption}</span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
function NetworkMetricsList({ refreshKey }: { refreshKey?: number }) {
  const [network_metrics, setNetworkMetrics] = useState<NetworkMetrics | null>(null);
  const [flash, setFlash] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [view, setView] = useState<"current" | "trend">("current");
  const [history, setHistory] = useState<NetworkMetricsHistoryEntry[] | null>(null);
  const [historyAvailable, setHistoryAvailable] = useState(true);

  useEffect(() => {
    fetchNetworkMetrics()
      .then((data) => {
        setNetworkMetrics(data);
        setTimeout(() => setFlash(true), 1700);
      })
      .catch(() => setUnavailable(true)); // 503 — node offline or metrics not yet computed
  }, [refreshKey]);

  // History only changes with the 24h snapshot cycle — fetch once on mount, not on every refresh.
  useEffect(() => {
    fetchNetworkMetricsHistory(90)
      .then((data) => setHistory(data))
      .catch(() => {
        // MongoDB not configured (503) — fall back to current-only, no toggle
        setHistoryAvailable(false);
        setView("current");
      });
  }, []);

  return (
    <div className={`card${flash ? " card--flash" : ""}`}>
      <h2>
        <span>Network Metrics</span>
        {historyAvailable && (
          <span className="velocity-toggle">
            <button
              className={`vt-btn${view === "current" ? " vt-btn--active" : ""}`}
              onClick={() => setView("current")}
            >
              Current
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
        <MetricsTrendView history={history} />
      ) : network_metrics ? (
        <>
          {/* ── Featured visuals ── */}
          <div className="nm-featured">
            <div className="nm-feature">
              <PulseRing
                score={network_metrics.pulse_score}
                gini={network_metrics.gini_coefficient}
                top10={network_metrics.top10_centralization}
                feeRate={network_metrics.median_fee_rate}
              />
              <div className="nm-feature-label">
                Pulse Score
                <InfoTooltip>
                  <span className="info-tooltip-title">What is the Pulse Score?</span>
                  <p className="info-tooltip-body">
                    A composite <strong>network health score</strong> from 0–100, computed from three pillars:
                    <span className="info-tooltip-formula">Equity 35% · Decentralization 35% · Fee Health 30%</span>
                    <strong>Equity</strong> — how evenly channel capacity is distributed across the network (lower Gini = higher score).<br /><br />
                    <strong>Decentralization</strong> — how much capacity is concentrated in the top 10 nodes. A network dominated by a few large hubs scores lower.<br /><br />
                    <strong>Fee Health</strong> — whether median fees sit in a healthy routing range (~500–5,000 ppm). Fees that are too low suggest spam risk; too high means poor usability.
                    <span className="info-tooltip-note">
                      ⚡ Computed from our LND node's graph — refreshed every 24 hours.
                    </span>
                  </p>
                </InfoTooltip>
              </div>
            </div>
            <div className="nm-feature">
              <LorenzCurve gini={network_metrics.gini_coefficient} />
              <div className="nm-feature-label">
                Gini&nbsp;
                <span className="nm-feature-val">{network_metrics.gini_coefficient.toFixed(3)}</span>
                <InfoTooltip>
                  <span className="info-tooltip-title">What is the Gini Coefficient?</span>
                  <p className="info-tooltip-body">
                    Borrowed from economics, the Gini coefficient measures <strong>wealth inequality</strong> —
                    here applied to Lightning channel capacity. It asks: how evenly is liquidity distributed across the network?
                    <span className="info-tooltip-formula">0.0 = perfectly equal · 1.0 = one node holds everything</span>
                    The <strong>Lorenz curve</strong> above visualises this — the further it bows away from
                    the diagonal equality line, the higher the inequality.
                    <br /><br />
                    Lightning typically scores <strong>0.75–0.90</strong>. A high score isn't necessarily bad —
                    large routing hubs naturally hold more capacity — but a score approaching 1.0 would
                    signal dangerous centralisation.
                    <span className="info-tooltip-note">
                      ⚡ Computed from channel capacities seen by our LND node.
                    </span>
                  </p>
                </InfoTooltip>
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
      ) : unavailable ? (
        <p className="card-empty">
          Node metrics unavailable — our LND node is unreachable or has not computed them yet.
        </p>
      ) : (
        <NetworkMetricsSkeleton />
      )}
    </div>
  );
}

export default NetworkMetricsList;
