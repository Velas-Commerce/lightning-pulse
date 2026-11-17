import { useEffect, useId, useRef, useState } from "react";

type TooltipPos = { top: number; left: number; above: boolean; arrowLeft: number };
type Props = { children: React.ReactNode };

const TOOLTIP_W = 280;
const TOOLTIP_H = 300; // generous estimate so flip triggers reliably
const GAP = 6;

// Hovering previews the tooltip. Clicking pins it, so it can be read at leisure and its
// text selected; it then stays until the icon is clicked again, a click lands outside,
// Escape is pressed, or the page scrolls or resizes (the box is positioned in screen
// coordinates, so it would otherwise be left hanging away from its icon).
function InfoTooltip({ children }: Props) {
  const [pos, setPos] = useState<TooltipPos | null>(null);
  const [pinned, setPinned] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const iconRef = useRef<HTMLButtonElement>(null);
  const boxId = useId();

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

  function close() {
    setPos(null);
    setPinned(false);
  }

  function toggle() {
    if (pinned) {
      close();
    } else {
      show();
      setPinned(true);
    }
  }

  useEffect(() => {
    if (!pinned) return;

    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      // Inside the wrapper counts as "not outside": that covers the icon and the box.
      if (!wrapRef.current?.contains(e.target as Node)) close();
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close();
        iconRef.current?.focus();
      }
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    // Capture, so a scroll in any container closes it, not just the window's.
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [pinned]);

  return (
    <span className="info-tooltip-wrap" ref={wrapRef}>
      <button
        ref={iconRef}
        type="button"
        className="info-tooltip-icon"
        onMouseEnter={() => { if (!pinned) show(); }}
        onMouseLeave={() => { if (!pinned) setPos(null); }}
        onFocus={() => { if (!pinned) show(); }}
        onBlur={() => { if (!pinned) setPos(null); }}
        onClick={toggle}
        aria-label="More information"
        aria-expanded={pinned}
        aria-describedby={pos ? boxId : undefined}
      >
        ⓘ
      </button>
      {pos && (
        <div
          id={boxId}
          role="tooltip"
          className={
            "info-tooltip-box" +
            (pos.above ? " info-tooltip-box--above" : "") +
            (pinned ? " info-tooltip-box--pinned" : "")
          }
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
