// Reusable skeleton building blocks — all share the shimmer CSS class.

export function SkeletonLine({ width = "100%", dimmed = false }: { width?: string | number; dimmed?: boolean }) {
  return (
    <div
      className="skeleton skeleton-line"
      style={{ width, opacity: dimmed ? 0.5 : 1 }}
    />
  );
}

export function SkeletonCircle({ size }: { size: number }) {
  return (
    <div
      className="skeleton skeleton-circle"
      style={{ width: size, height: size }}
    />
  );
}

export function SkeletonBlock({ width = "100%", height }: { width?: string | number; height: number }) {
  return (
    <div
      className="skeleton skeleton-block"
      style={{ width, height }}
    />
  );
}

// A key-value row (label left, value right) — matches the .card p layout
export function SkeletonStatRow({ labelWidth = "45%", valWidth = "30%" }: { labelWidth?: string; valWidth?: string }) {
  return (
    <div className="skeleton-row">
      <div className="skeleton skeleton-line" style={{ width: labelWidth, marginBottom: 0 }} />
      <div className="skeleton skeleton-line" style={{ width: valWidth, marginBottom: 0 }} />
    </div>
  );
}

// N table rows (name | value | value)
export function SkeletonTableRows({ rows }: { rows: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-row">
          <div className="skeleton skeleton-line" style={{ width: "40%", marginBottom: 0 }} />
          <div className="skeleton skeleton-line" style={{ width: "22%", marginBottom: 0 }} />
          <div className="skeleton skeleton-line" style={{ width: "12%", marginBottom: 0 }} />
        </div>
      ))}
    </>
  );
}
