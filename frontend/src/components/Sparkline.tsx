import { useEffect, useId, useState } from "react";

// Compact trend line for the report card's slow indices.
//
// Not a variant of TrendChart: that one locks a 200x110 viewBox with no explicit
// height, so at this width it renders ~92px tall, and its axes, tick labels and
// crosshair are unconditional. Two cards depend on its exact rendering, so it is
// left alone. The house idioms are shared though — pathLength=1 draw-on with an
// ease-out cubic on requestAnimationFrame.
//
// Values are plotted index-spaced rather than time-spaced. The slow indices are
// already smooth and their series lengths differ (our own metrics are daily; the
// mempool-derived ones arrive far more sparsely), so even spacing reads better
// than gaps, and the caption carries the window rather than an axis.
export function Sparkline({ values }: { values: number[] }) {
  const W = 168;
  const H = 26;
  const pad = 3;

  // TrendChart hardcodes id="cap-glow"; four sparklines plus that chart on one
  // page would all resolve to whichever <defs> the document defines first.
  const glowId = `spark-glow-${useId()}`;

  const [animOffset, setAnimOffset] = useState(1);
  useEffect(() => {
    const duration = 1200;
    const start = performance.now();
    function frame(now: number) {
      const t = Math.min((now - start) / duration, 1);
      setAnimOffset(Math.pow(1 - t, 3));
      if (t < 1) requestAnimationFrame(frame);
    }
    const id = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(id);
  }, [values]);

  if (values.length < 2) return null;

  const lo = Math.min(...values);
  const hi = Math.max(...values);
  // Flat series still render as a centred line rather than dividing by zero.
  const span = hi - lo || Math.abs(hi) * 0.02 || 1;

  const x = (i: number) => (i / (values.length - 1)) * W;
  const y = (v: number) => pad + (1 - (v - lo) / span) * (H - pad * 2);

  const d = values
    .map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`)
    .join(" ");
  const lastX = x(values.length - 1);
  const lastY = y(values[values.length - 1]);

  return (
    // Scales uniformly: stretching to a fixed pixel height would turn the end
    // dot into an ellipse whenever the grid column is wider than the viewBox.
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", height: "auto", display: "block" }}
      aria-hidden="true"
    >
      <defs>
        <filter id={glowId} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <path
        d={d}
        fill="none"
        stroke="var(--amber)"
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={animOffset}
      />

      {/* Latest value, fading in as the line finishes drawing */}
      <circle
        cx={lastX}
        cy={lastY}
        r={2.2}
        fill="var(--lightning)"
        filter={`url(#${glowId})`}
        opacity={1 - animOffset}
      />
    </svg>
  );
}
