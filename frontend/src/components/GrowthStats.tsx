import { useState, useEffect } from "react";
import type { LightningGrowthStats, BtcPrice } from "../types";
import { fetchGrowthStats, fetchBtcPrice } from "../api";

function GrowthStats() {
  const [growth_stats, setGrowthStats] = useState<LightningGrowthStats | null>(null);
  const [price, setPrice] = useState<BtcPrice | null>(null);

  useEffect(() => {
    fetchGrowthStats().then((data) => setGrowthStats(data));
    fetchBtcPrice().then((data) => setPrice(data));
  }, []);

  return (
    <div className="card">
      <h2>Market &amp; Growth</h2>
      {price && (
        <>
          <p><span>BTC Price</span><span className="val">${price.USD.toLocaleString()} USD</span></p>
          <p><span>Sats per Dollar</span><span className="val">{Math.round(100_000_000 / price.USD).toLocaleString()} sats</span></p>
        </>
      )}
      {growth_stats && (
        <>
          <p><span>Users with Access</span><span className="val">{growth_stats.num_lightning_users.toLocaleString()}</span></p>
          <p><span>Average Payment</span><span className="val">${growth_stats.avg_transaction_usd.toLocaleString()}</span></p>
          <p className="section-label">Monthly Volume</p>
          <ul>
            {growth_stats.monthly_volume.map((entry) => (
              <li key={entry.date}>
                <span className="label">{entry.date}</span>
                <span className="val">${entry.volume_usd.toLocaleString()} · {entry.transactions.toLocaleString()} txns</span>
              </li>
            ))}
          </ul>
          <p className="section-label">Sources</p>
          <ul className="sources">
            {growth_stats.sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default GrowthStats;
