import { useEffect, useState } from "react";

// Compact trend line for the report card's slow indices.
//
// Not a variant of TrendChart: that one locks a 200x110 viewBox with no explicit
// height, so at this width it renders ~92px tall, and its axes, tick labels and
// crosshair are unconditional. Two cards depend on its exact rendering, so it is
// left alone. The house draw-on idiom is shared though — pathLength=1 with an
// ease-out cubic on requestAnimationFrame.
//
// Shape only, deliberately. There is no axis, no endpoint marker and no hover: the
// line says which way the metric has been going, and the caption beneath it carries
// every number a reader needs — where the latest reading ranks, how far the window
// moved, and how many readings it holds. An endpoint dot was tried and removed; it
// marked the latest value, which is already printed in full above the line, so it
// read as though it meant something more.
//
// Values are plotted index-spaced rather than time-spaced. The indices are already
// smooth and their series lengths differ (our own metrics are daily; the
// mempool-derived ones arrive far more sparsely), so even spacing reads better than
// gaps, and the caption carries the window rather than an axis.
export function Sparkline({ values }: { values: number[] }) {
  const W = 168;
  const H = 26;
  const padX = 1; // just enough that the stroke is not clipped at the edges
  const padY = 3;

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

  const x = (i: number) => padX + (i / (values.length - 1)) * (W - padX * 2);
  const y = (v: number) => padY + (1 - (v - lo) / span) * (H - padY * 2);

  const d = values
    .map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`)
    .join(" ");

  return (
    // Scales uniformly; height follows from the viewBox aspect ratio.
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", height: "auto", display: "block" }}
      aria-hidden="true"
    >
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
    </svg>
  );
}
