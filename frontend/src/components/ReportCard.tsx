import { useEffect, useState } from "react";
import type { CapacityTrend, DailyReport, SlowIndex } from "../types";
import { fetchDailyReport } from "../api";
import { CapacityChart } from "./CapacityChart";
import { Sparkline } from "./Sparkline";
import { SkeletonBlock, SkeletonLine } from "./Skeleton";
import InfoTooltip from "./InfoTooltip";

const SATS_PER_BTC = 100_000_000;

// Mirrors MIN_LIVE_DAYS in services/report_card.py — keep both in sync.
const MIN_LIVE_DAYS = 14;

/** Capacity reads naturally in BTC when it is large and in sats when it is not. */
function fmtCapacity(btc: number): string {
  if (btc >= 1) return `${btc.toFixed(2)} BTC`;
  const sats = Math.round(btc * SATS_PER_BTC);
  if (sats >= 1_000_000) return `${(sats / 1_000_000).toFixed(2)}M sats`;
  return `${sats.toLocaleString()} sats`;
}

function ordinal(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// Formatted straight from the ISO parts rather than through Date + toLocaleDateString.
// These are UTC calendar dates, and routing them through a Date risks shifting them
// into the viewer's zone — the exact confusion this card's framing exists to avoid.
const fmtDay = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${Number(d)} ${MONTHS[Number(m) - 1]}`;
};

const fmtDayFull = (iso: string) => {
  const [y, m, d] = iso.split("-");
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
};

/** Where the latest reading sits, and how far the window actually moved.
 *
 * A percentile alone is unitless: it says where in the range you are while saying
 * nothing about whether the range is worth caring about. Those differ enormously
 * here — Gini's whole 91-day range is 2.3% of its value, so "99th percentile" is a
 * 1.1% move, while Capacity's range is 22.6% and its position means something. The
 * change is shown alongside so the reader can tell the two cases apart.
 *
 * At the very edges the ordinal reads like a bug — the minimum scores exactly 0,
 * and because only strictly-lower values count, the maximum scores 99 and never
 * 100 — so those are stated in words instead.
 */
function positionOf(series: number[], percentile: number): string {
  const n = series.length;
  const last = series[n - 1];
  // A percentile and a count are different units; "98th of 91" reads as nonsense.
  if (last >= Math.max(...series)) return `highest of ${n} readings`;
  if (last <= Math.min(...series)) return `lowest of ${n} readings`;
  return `${ordinal(percentile)} percentile · ${n} readings`;
}

/** A true minus sign, matching the server's copy, so a figure reads the same in both. */
const signedPct = (pct: number) => `${pct >= 0 ? "+" : "−"}${Math.abs(pct).toFixed(1)}%`;

function changeOf(series: number[]): string | null {
  const first = series[0];
  const last = series[series.length - 1];
  if (!first) return null;
  const pct = ((last - first) / Math.abs(first)) * 100;
  if (!isFinite(pct)) return null;
  return signedPct(pct);
}

/** Each slow index carries its own units; there is no sensible shared format. */
function formatIndex(s: SlowIndex): string {
  switch (s.key) {
    case "gini":
      return s.value.toFixed(3);
    case "top10":
      return `${(s.value * 100).toFixed(1)}%`;
    case "velocity":
      return `${s.value.toFixed(2)}×`;
    default:
      return s.value.toLocaleString();
  }
}

/** The capacity tile: the level, and how far it moved over the recent leg. */
function capacityFigure(c: CapacityTrend) {
  const moved = c.change_pct !== null && c.change_days !== null;
  return {
    key: "Network capacity",
    value: `${Math.round(c.value).toLocaleString()} BTC`,
    sub: moved
      ? `${signedPct(c.change_pct as number)} over ${c.change_days} days`
      : `as of ${fmtDay(c.as_of)}`,
    tone: moved ? ((c.change_pct as number) < 0 ? "dn" : "up") : undefined,
  };
}

/** Capacity against its trend: a subheading in the summary, the analysis in words, and
 *  the chart that backs it. */
function CapacityBlock({ c }: { c: CapacityTrend }) {
  return (
    <section className="rc-capacity">
      <h3 className="rc-subheading">Network capacity</h3>
      <div className="rc-capacity-body">
        <p className="rc-subline">{c.analysis}</p>
        <CapacityChart
          dates={c.dates}
          values={c.series}
          recentDays={c.change_days}
          longDays={c.long_days}
        />
      </div>
    </section>
  );
}

function Headline({ text, highlight }: { text: string; highlight: string | null }) {
  const at = highlight ? text.indexOf(highlight) : -1;
  if (at < 0) return <p className="rc-headline">{text}</p>;
  return (
    <p className="rc-headline">
      {text.slice(0, at)}
      <span className="rc-hl">{highlight}</span>
      {text.slice(at + highlight!.length)}
    </p>
  );
}

/** Weekday, date, block range and the explicit UTC window. */
function stampFor(report: DailyReport): string {
  const range =
    report.block_from > 0 && report.block_from <= report.block_height
      ? `blocks ${report.block_from.toLocaleString()}–${report.block_height.toLocaleString()}`
      : `block ${report.block_height.toLocaleString()}`;
  return `${report.weekday} ${fmtDayFull(report.date)} · ${range} · 00:00–23:59 UTC`;
}

function ReportCardSkeleton() {
  return (
    <>
      <SkeletonLine width="70%" />
      <SkeletonLine width="90%" dimmed />
      <SkeletonBlock height={64} />
      <SkeletonBlock height={70} />
    </>
  );
}

function VerdictStep({ report }: { report: DailyReport }) {
  const { flow, baseline, verdict } = report;

  // The baseline is only trustworthy once enough days were collected live;
  // backfilled days undercount, so until then no figure claims a comparison.
  const calibrating = baseline.live_days < MIN_LIVE_DAYS;

  // Read straight from the report rather than re-derived from `hourly`. Deriving
  // them here meant falling back to btc_in / opens whenever hourly was absent —
  // a *mean* under a "Median open" label, and the distribution is skewed about 4:1,
  // so that was not a rounding difference. The backend now stores both per day.
  // Sizes were stored later than counts, so they have their own, shorter history and
  // their own calibration — live_days alone would claim a baseline that is not there.
  const sizesReady = baseline.sizes_days >= MIN_LIVE_DAYS;
  const sizeSub = (label: string, typical: number) =>
    sizesReady
      ? `vs ${fmtCapacity(typical)} typical`
      : `${label} · ${baseline.sizes_days} of ${MIN_LIVE_DAYS} days`;

  const medianOpen = flow.median_open;
  const largestOpen = flow.largest_open > 0 ? flow.largest_open : null;

  const figures: { key: string; value: string; sub: string; tone?: string }[] = [
    {
      key: "Opened",
      value: flow.opens.toLocaleString(),
      sub: calibrating
        ? "channels"
        : `vs ${Math.round(baseline.opens_median).toLocaleString()} typical`,
      tone: "up",
    },
    // Sits beside Opened so the two halves of the day's flow read together.
    report.closes_available
      ? {
          key: "Closed",
          value: flow.closes.toLocaleString(),
          sub: `${flow.btc_out.toFixed(1)} BTC left`,
          tone: "dn",
        }
      : { key: "Closed", value: "—", sub: "close detection pending", tone: "dim" },
    {
      key: "New capacity",
      value: `${flow.btc_in.toFixed(1)} BTC`,
      sub: calibrating
        ? "entered the network"
        : `vs ${baseline.btc_in_median.toFixed(1)} typical`,
      tone: "up",
    },
    // Beside "New capacity" on purpose: one is the day's inflow, the other the network
    // total and where it has been heading.
    ...(report.capacity ? [capacityFigure(report.capacity)] : []),
    ...(medianOpen > 0
      ? [
          {
            key: "Median open",
            value: fmtCapacity(medianOpen),
            sub: sizeSub("per channel", baseline.median_open_typical),
          },
        ]
      : []),
    ...(largestOpen !== null
      ? [
          {
            key: "Largest open",
            value: fmtCapacity(largestOpen),
            sub: sizeSub("single channel", baseline.largest_open_typical),
          },
        ]
      : []),
  ];

  return (
    <>
      <Headline text={verdict.headline} highlight={verdict.highlight} />
      <p className="rc-subline">{verdict.subline}</p>

      {report.capacity && <CapacityBlock c={report.capacity} />}

      {/* The day's figures close the summary, under the capacity trend. */}
      <div className="rc-figures">
        {figures.map((f) => (
          <div className="rc-figure" key={f.key}>
            <span className="rc-figure-key">{f.key}</span>
            <div className={`rc-figure-value${f.tone ? ` rc-figure-value--${f.tone}` : ""}`}>
              {f.value}
            </div>
            <div className="rc-figure-sub">{f.sub}</div>
          </div>
        ))}
      </div>
    </>
  );
}

/** One slow index on its own panel. */
function SlowStep({ index: s }: { index: SlowIndex }) {
  return (
    <div className="rc-panel">
      <span className="rc-slow-label">{s.label}</span>
      <div className="rc-panel-value">{formatIndex(s)}</div>
      <Sparkline values={s.series} />
      <span className="rc-slow-caption">
        <b>{positionOf(s.series, s.percentile)}</b>
        {changeOf(s.series) && ` · ${changeOf(s.series)}`}
        {/* Mempool-derived indices run weeks behind the day being reported;
            say so rather than letting them pass as current. */}
        {s.stale_days > 2 && ` · as of ${fmtDay(s.as_of)}`}
      </span>
      {s.analysis && <p className="rc-subline rc-panel-analysis">{s.analysis}</p>}
    </div>
  );
}

function ReportCard() {
  const [report, setReport] = useState<DailyReport | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [step, setStep] = useState(0);

  // Fetched once on mount, not on refreshKey — the report changes once a day.
  useEffect(() => {
    fetchDailyReport()
      .then((data) => setReport(data))
      .catch(() => setUnavailable(true)); // 503: no database, or no complete day yet
  }, []);

  // The nav appears on its own once there is more than one step.
  const steps = report
    ? [
        {
          key: "verdict",
          label: "Verdict",
          node: <VerdictStep report={report} />,
          // No coverage line under this slide: its provenance is in the info tooltip.
          coverage: "",
        },
        ...report.slow.map((s) => ({
          key: s.key,
          label: s.label,
          node: <SlowStep index={s} />,
          coverage: s.source,
        })),
      ]
    : [];

  // Nothing to say yet — stay out of the way rather than showing a broken card.
  if (unavailable) return null;

  return (
    <section className="card report-card">
      <h2>
        <span>
          Daily Report
          <InfoTooltip>
            <div className="info-tooltip-title">Daily report card</div>
            <div className="info-tooltip-body">
              What happened on Lightning over one complete UTC day, and whether it was
              unusual. The block range in the header is the exact window measured.
              Channel opens are decoded from each channel's short channel ID, which
              encodes the block that confirmed its funding transaction.
            </div>
            <div className="info-tooltip-formula">
              deviation = 0.6745 × (value − median) ÷ MAD
            </div>
            <div className="info-tooltip-note">
              ⚡ Median and MAD rather than mean and standard deviation, because channel
              flow is spiky.
            </div>
            {report && <div className="info-tooltip-note">{report.coverage_note}</div>}
          </InfoTooltip>
        </span>
        {steps.length > 1 && (
          <span className="rc-nav">
            <span className="rc-step-name">
              {steps[step].label} · {step + 1}/{steps.length}
            </span>
            <span className="rc-dots">
              {steps.map((s, i) => (
                <button
                  key={s.key}
                  className={`rc-dot${i === step ? " rc-dot--active" : ""}`}
                  aria-current={i === step}
                  aria-label={s.label}
                  title={s.label}
                  onClick={() => setStep(i)}
                />
              ))}
            </span>
            <button
              className="vt-btn"
              aria-label="Previous"
              onClick={() => setStep((s) => (s - 1 + steps.length) % steps.length)}
            >
              ‹
            </button>
            <button
              className="vt-btn"
              aria-label="Next"
              onClick={() => setStep((s) => (s + 1) % steps.length)}
            >
              ›
            </button>
          </span>
        )}
      </h2>

      {report && <p className="rc-stamp">{stampFor(report)}</p>}

      {report ? steps[step].node : <ReportCardSkeleton />}

      {report && steps[step].coverage && (
        <p className="rc-coverage">{steps[step].coverage}</p>
      )}
    </section>
  );
}

export default ReportCard;
