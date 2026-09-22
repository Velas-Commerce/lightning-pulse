import { useEffect, useState } from "react";
import type { DailyReport, SlowIndex } from "../types";
import { fetchDailyReport } from "../api";
import { Sparkline } from "./Sparkline";
import { SkeletonBlock, SkeletonLine } from "./Skeleton";
import InfoTooltip from "./InfoTooltip";

const SATS_PER_BTC = 100_000_000;

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

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });

/** Each slow index carries its own units; there is no sensible shared format. */
function formatIndex(s: SlowIndex): string {
  switch (s.key) {
    case "gini":
      return s.value.toFixed(3);
    case "top10":
      return `${(s.value * 100).toFixed(1)}%`;
    case "velocity":
      return `${s.value.toFixed(2)}×`;
    case "capacity":
      return `${Math.round(s.value / SATS_PER_BTC).toLocaleString()} BTC`;
    default:
      return s.value.toLocaleString();
  }
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
  const { flow, baseline, verdict, slow } = report;

  // The baseline is only trustworthy once enough days were collected live;
  // backfilled days undercount, so until then no figure claims a comparison.
  const calibrating = baseline.live_days < 14;

  const opens = flow.hourly ? flow.hourly.flatMap((h) => h.opens) : [];
  const sorted = [...opens].sort((a, b) => a - b);
  const medianOpen = sorted.length
    ? sorted[Math.floor(sorted.length / 2)]
    : flow.btc_in / Math.max(flow.opens, 1);
  const largestOpen = sorted.length ? sorted[sorted.length - 1] : null;

  const figures: { key: string; value: string; sub: string; tone?: string }[] = [
    {
      key: "Opened",
      value: flow.opens.toLocaleString(),
      sub: calibrating
        ? "channels"
        : `vs ${Math.round(baseline.opens_median).toLocaleString()} typical`,
      tone: "up",
    },
    {
      key: "New capacity",
      value: `${flow.btc_in.toFixed(1)} BTC`,
      sub: calibrating
        ? "entered the network"
        : `vs ${baseline.btc_in_median.toFixed(1)} typical`,
      tone: "up",
    },
    { key: "Median open", value: fmtCapacity(medianOpen), sub: "per channel" },
    ...(largestOpen !== null
      ? [{ key: "Largest open", value: fmtCapacity(largestOpen), sub: "single channel" }]
      : []),
    ...(!report.closes_available
      ? [{ key: "Closed", value: "—", sub: "close detection pending", tone: "dim" }]
      : []),
  ];

  return (
    <>
      <p className="rc-headline">{verdict.headline}</p>
      <p className="rc-subline">{verdict.subline}</p>

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

      <div className="rc-slow">
        {slow.map((s) => (
          <div className="rc-slow-item" key={s.key}>
            <div className="rc-slow-head">
              <span className="rc-slow-label">{s.label}</span>
              <span className="rc-slow-value">{formatIndex(s)}</span>
            </div>
            <Sparkline values={s.series} />
            <span className="rc-slow-caption">
              <b>{ordinal(s.percentile)}</b> percentile · {s.series.length} readings
              {/* Mempool-derived indices run weeks behind; say so rather than
                  letting a card headlined "last 24 hours" imply otherwise. */}
              {s.stale_days > 2 && ` · as of ${fmtDay(s.as_of)}`}
            </span>
          </div>
        ))}
      </div>
    </>
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

  // Flow and Shape steps push onto this; the nav appears on its own once they do.
  const steps = report ? [{ key: "verdict", node: <VerdictStep report={report} /> }] : [];

  // Nothing to say yet — stay out of the way rather than showing a broken card.
  if (unavailable) return null;

  return (
    <section className="card report-card">
      <h2>
        <span>
          Daily Report
          {report && ` · ${fmtDay(report.date)}`}
          <InfoTooltip>
            <div className="info-tooltip-title">Daily report card</div>
            <div className="info-tooltip-body">
              What happened on Lightning in the last complete UTC day, and whether it
              was unusual. Channel opens are decoded from each channel's short channel
              ID, which encodes the block that confirmed its funding transaction.
            </div>
            <div className="info-tooltip-formula">
              deviation = 0.6745 × (value − median) ÷ MAD
            </div>
            <div className="info-tooltip-note">
              ⚡ Median and MAD rather than mean and standard deviation, because channel
              flow is spiky. Counts are what our own node gossiped, not the whole network.
            </div>
          </InfoTooltip>
        </span>
        {steps.length > 1 && (
          <span className="rc-nav">
            <span className="rc-dots">
              {steps.map((s, i) => (
                <button
                  key={s.key}
                  className={`rc-dot${i === step ? " rc-dot--active" : ""}`}
                  aria-current={i === step}
                  aria-label={`Step ${i + 1}`}
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

      {report ? steps[step].node : <ReportCardSkeleton />}

      {report && <p className="rc-coverage">{report.coverage_note}</p>}
    </section>
  );
}

export default ReportCard;
