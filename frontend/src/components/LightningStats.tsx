import { useState, useEffect } from "react";
import type { LightningStatsResponse } from "../types";
import { fetchLightningStats } from "../api";

function LightningStats() {
  const [lightning_stats, setLightningStats] = useState<LightningStatsResponse | null>(null);

  useEffect(() => {
    fetchLightningStats().then((data) => setLightningStats(data));
  }, []);

  return (
    <div>
      <h2>Lightning Stats</h2>
      {lightning_stats && <p>Channels: {lightning_stats.latest.channel_count.toLocaleString()}</p>}
    </div>
  );
}

export default LightningStats;