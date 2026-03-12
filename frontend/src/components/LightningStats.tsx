import { useState, useEffect } from "react";
import type { LightningStatsResponse } from "../types";
import { fetchLightningStats } from "../api";

function LightningStats() {
  const [lightning_stats, setLightningStats] = useState<LightningStatsResponse | null>(null);

  useEffect(() => {
    fetchLightningStats().then((data) => setLightningStats(data));
  }, []);

  return (
    <div className="card">
      <h2>Lightning Stats</h2>
      {lightning_stats && (
        <>
          <p><span>Channels</span><span className="val">{lightning_stats.latest.channel_count.toLocaleString()}</span></p>
          <p><span>Nodes</span><span className="val">{lightning_stats.latest.node_count.toLocaleString()}</span></p>
          <p><span>Total Capacity</span><span className="val">{lightning_stats.latest.total_capacity.toLocaleString()} sats</span></p>
          <p><span>Avg Capacity</span><span className="val">{lightning_stats.latest.avg_capacity.toLocaleString()} sats</span></p>
          <p><span>Avg Fee Rate</span><span className="val">{lightning_stats.latest.avg_fee_rate.toLocaleString()} ppm</span></p>
        </>
      )}
    </div>
  );
}

export default LightningStats;
