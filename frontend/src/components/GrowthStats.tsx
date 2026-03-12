import { useState, useEffect } from "react";
import type { LightningGrowthStats } from "../types";
import { fetchGrowthStats } from "../api";

function GrowthStats() {
  const [growth_stats, setGrowthStats] = useState<LightningGrowthStats | null>(null);

  useEffect(() => {
    fetchGrowthStats().then((data) => setGrowthStats(data));
  }, []);

  return (
    <div>
      <h2>Lightning Network Growth Stats</h2>
      {growth_stats && (
        <>
          <p>Users with Access: {growth_stats.num_lightning_users.toLocaleString()}</p>
          <p>Average Payment: ${growth_stats.avg_transaction_usd.toLocaleString()}</p>
          <p>Monthly Volume</p>
          <ul>
            {growth_stats.monthly_volume.map((entry) => (
              <li key={entry.date}>
                {entry.date}: ${entry.volume_usd.toLocaleString()} ({entry.transactions.toLocaleString()} txns)
              </li>
            ))}
          </ul>
          <p>Sources</p>
          <ul>
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