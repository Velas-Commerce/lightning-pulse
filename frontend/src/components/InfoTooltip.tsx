import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

// The icon's position on screen when the tooltip was opened or last followed it.
type Anchor = { top: number; bottom: number; left: number; width: number };
type Props = { children: React.ReactNode };

const TOOLTIP_W = 280;
const GAP = 6;
const EDGE = 8; // minimum distance kept from the viewport edge
const HOVER_QUIET_MS = 250; // hover is ignored this long after a close; see closedAtRef

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(value, max));
}

// Hovering previews the tooltip. Clicking pins it, so it can be read at leisure and its
// text selected; it then stays until the icon is clicked again, a click lands outside,
// Escape is pressed, or the icon scrolls out of view. While pinned it follows the icon
// as the page scrolls.
//
// The box is rendered into document.body, not beside the icon. Cards set
// `overflow: hidden` and keep the transform from their fadeUp entry animation, which
// makes the card the containing block for `position: fixed` descendants: the box was
// then placed from the card's corner instead of the screen's, and clipped by the card.
// Outside the card it can neither be clipped nor misplaced, however short the card is.
function InfoTooltip({ children }: Props) {
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const [pinned, setPinned] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const iconRef = useRef<HTMLButtonElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const boxId = useId();
  // When the tooltip last closed. Removing the box makes the browser re-check what is
  // under a resting pointer and fire a synthetic mouseenter on the icon, which would
  // open the tooltip straight back up; hover is ignored for a moment after any close.
  const closedAtRef = useRef(0);

  function measure(): Anchor | null {
    const rect = iconRef.current?.getBoundingClientRect();
    return rect
      ? { top: rect.top, bottom: rect.bottom, left: rect.left, width: rect.width }
      : null;
  }

  function show() {
    setAnchor(measure());
  }

  function close() {
    closedAtRef.current = performance.now();
    setAnchor(null);
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

    const isInside = (target: EventTarget | null) =>
      target instanceof Node &&
      (wrapRef.current?.contains(target) || boxRef.current?.contains(target));

    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      if (!isInside(e.target)) close();
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close();
        // Hand focus back to the icon without scrolling to it: a scroll here would
        // reach onViewportChange below before this effect has been torn down.
        iconRef.current?.focus({ preventScroll: true });
      }
    };
    // Follow the icon rather than closing on every scroll event: unrelated scrolling
    // (and the tooltip's own scrolling) must not unpin it.
    const onViewportChange = (e: Event) => {
      if (isInside(e.target)) return;
      const next = measure();
      if (!next || next.bottom < 0 || next.top > window.innerHeight) close();
      // Only move a box that is still open. This listener can fire once more after
      // close() has been queued, and must not bring a closed box back.
      else setAnchor((current) => (current ? next : current));
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    // Capture, so a scroll in any container is seen, not just the window's.
    window.addEventListener("scroll", onViewportChange, true);
    window.addEventListener("resize", onViewportChange);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", onViewportChange, true);
      window.removeEventListener("resize", onViewportChange);
    };
  }, [pinned]);

  // Place on whichever side has more room. Anchoring the above case by its bottom edge
  // needs no estimate of the box's height; the space on that side caps its height, and
  // anything longer scrolls inside the box instead of running off the screen.
  let box: React.ReactNode = null;
  if (anchor) {
    const spaceAbove = anchor.top;
    const spaceBelow = window.innerHeight - anchor.bottom;
    const above = spaceAbove > spaceBelow;
    const left = clamp(
      anchor.left + anchor.width / 2 - TOOLTIP_W / 2,
      EDGE,
      window.innerWidth - TOOLTIP_W - EDGE,
    );
    const arrowLeft = Math.round(anchor.left + anchor.width / 2 - left);
    const maxHeight = Math.max(120, (above ? spaceAbove : spaceBelow) - GAP - EDGE);

    box = createPortal(
      <div
        ref={boxRef}
        id={boxId}
        role="tooltip"
        className={
          "info-tooltip-box" +
          (above ? " info-tooltip-box--above" : "") +
          (pinned ? " info-tooltip-box--pinned" : "")
        }
        style={{
          position: "fixed",
          left,
          ...(above
            ? { bottom: window.innerHeight - anchor.top + GAP }
            : { top: anchor.bottom + GAP }),
          maxHeight,
          ["--arrow-left" as string]: `${arrowLeft}px`,
        }}
      >
        <div className="info-tooltip-scroll">{children}</div>
      </div>,
      document.body,
    );
  }

  return (
    <span className="info-tooltip-wrap" ref={wrapRef}>
      <button
        ref={iconRef}
        type="button"
        className="info-tooltip-icon"
        onMouseEnter={() => {
          if (!pinned && performance.now() - closedAtRef.current > HOVER_QUIET_MS) show();
        }}
        onMouseLeave={() => { if (!pinned) setAnchor(null); }}
        onFocus={() => { if (!pinned) show(); }}
        onBlur={() => { if (!pinned) setAnchor(null); }}
        onClick={toggle}
        aria-label="More information"
        aria-expanded={pinned}
        aria-describedby={anchor ? boxId : undefined}
      >
        ⓘ
      </button>
      {box}
    </span>
  );
}

export default InfoTooltip;
