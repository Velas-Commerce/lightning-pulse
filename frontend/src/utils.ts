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
