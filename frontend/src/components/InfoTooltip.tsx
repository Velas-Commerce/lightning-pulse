import { useState, useRef } from "react";

type Props = {
  children: React.ReactNode;
};

function InfoTooltip({ children }: Props) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const iconRef = useRef<HTMLButtonElement>(null);

  function show() {
    const rect = iconRef.current?.getBoundingClientRect();
    if (!rect) return;
    setPos({
      top: rect.bottom + 8,
      left: rect.left + rect.width / 2,
    });
  }

  function hide() {
    setPos(null);
  }

  return (
    <span className="info-tooltip-wrap">
      <button
        ref={iconRef}
        className="info-tooltip-icon"
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        aria-label="More information"
      >
        ⓘ
      </button>
      {pos && (
        <div
          className="info-tooltip-box"
          style={{ position: "fixed", top: pos.top, left: pos.left }}
        >
          {children}
        </div>
      )}
    </span>
  );
}

export default InfoTooltip;
