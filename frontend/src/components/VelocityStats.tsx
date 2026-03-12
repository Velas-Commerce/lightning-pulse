import { useState, useEffect } from "react";
import type { LiquidityVelocity } from "../types";
import { fetchVelocityStats } from "../api";

function VelocityStats() {
  const [velocity_stats, setVelocityStats] = useState<LiquidityVelocity | null>(null);

  useEffect(() => {
    fetchVelocityStats().then((data) => setVelocityStats(data));
  }, []);

  return (
    <div>
      <h2>Liquidity Velocity</h2>
      {velocity_stats && (
        <>
          <p>Velocity: {velocity_stats.velocity.toLocaleString()}</p>
          <p>Monthly Volume: {velocity_stats.monthly_volume_usd.toLocaleString()}</p>
          <p>Capacity: {velocity_stats.capacity_sats.toLocaleString()} SATS?</p>
        </>
      )}
    </div>
  );
}

export default VelocityStats;