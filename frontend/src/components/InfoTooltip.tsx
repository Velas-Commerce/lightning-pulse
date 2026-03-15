import { useState, useRef } from "react";

type TooltipPos = { top: number; left: number; above: boolean; arrowLeft: number };
type Props = { children: React.ReactNode };

const TOOLTIP_W = 280;
const TOOLTIP_H = 300; // generous estimate so flip triggers reliably
const GAP = 6;

function InfoTooltip({ children }: Props) {
  const [pos, setPos] = useState<TooltipPos | null>(null);
  const iconRef = useRef<HTMLButtonElement>(null);

  function show() {
    const rect = iconRef.current?.getBoundingClientRect();
    if (!rect) return;

    // Show above if there's more space above the icon than below
    const above = rect.top > window.innerHeight - rect.bottom;

    // Fully calculate Y in JS — no CSS translateY needed
    const top = above
      ? rect.top - GAP - TOOLTIP_H
      : rect.bottom + GAP;

    // Calculate left edge directly (no CSS transform centering)
    const rawLeft = rect.left + rect.width / 2 - TOOLTIP_W / 2;
    const left = Math.max(8, Math.min(rawLeft, window.innerWidth - TOOLTIP_W - 8));

    // Arrow offset: where the icon center is relative to the tooltip left edge
    const arrowLeft = Math.round(rect.left + rect.width / 2 - left);

    setPos({ top, left, above, arrowLeft });
  }

  return (
    <span className="info-tooltip-wrap">
      <button
        ref={iconRef}
        className="info-tooltip-icon"
        onMouseEnter={show}
        onMouseLeave={() => setPos(null)}
        onFocus={show}
        onBlur={() => setPos(null)}
        aria-label="More information"
      >
        ⓘ
      </button>
      {pos && (
        <div
          className={`info-tooltip-box${pos.above ? " info-tooltip-box--above" : ""}`}
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            ["--arrow-left" as string]: `${pos.arrowLeft}px`,
          }}
        >
          {children}
        </div>
      )}
    </span>
  );
}

export default InfoTooltip;
