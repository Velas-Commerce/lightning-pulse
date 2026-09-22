/** Convert satoshis to a formatted BTC string.
 *  ≥ 1 BTC  →  "1,234.56 BTC"
 *  < 1 BTC  →  "0.0234 BTC"  (4 decimal places)
 */
export function satsToBtc(sats: number): string {
  const btc = sats / 100_000_000;
  if (btc >= 1) {
    return btc.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " BTC";
  }
  return btc.toFixed(4) + " BTC";
}

export type TrendPoint = { t: number; v: number; ma: number };

export const fmtDate = (t: number) => new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });

/** One value per UTC day (last snapshot wins) — backend restarts can persist several per day */
export function dailyValues(entries: { recorded_at: string; value: number }[]): { t: number; v: number }[] {
  const byDay = new Map<string, { t: number; v: number }>();
  for (const e of entries) {
    const date = new Date(e.recorded_at);
    if (e.value > 0) {
      byDay.set(date.toISOString().slice(0, 10), { t: date.getTime(), v: e.value });
    }
  }
  return [...byDay.values()].sort((a, b) => a.t - b.t);
}

/** Attach a 7-day trailing moving average, which the trend line is drawn from */
export function movingAverage(daily: { t: number; v: number }[]): TrendPoint[] {
  return daily.map((p, i) => {
    const from = Math.max(0, i - 6);
    let sum = 0;
    for (let j = from; j <= i; j++) sum += daily[j].v;
    return { ...p, ma: sum / (i - from + 1) };
  });
}
