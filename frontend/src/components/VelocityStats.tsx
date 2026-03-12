import { useState, useEffect } from "react";
import type { LiquidityVelocity } from "../types";
import { fetchVelocityStats } from "../api";

function VelocityStats() {
  const [velocity_stats, setVelocityStats] = useState<LiquidityVelocity | null>(null);

  useEffect(() => {
    fetchVelocityStats().then((data) => setVelocityStats(data));
  }, []);

  return (
    <div className="card">
      <h2>Liquidity Velocity</h2>
      {velocity_stats && (
        <>
          <p><span>Velocity</span><span className="val">{velocity_stats.velocity.toLocaleString()}</span></p>
          <p><span>Monthly Volume</span><span className="val">${velocity_stats.monthly_volume_usd.toLocaleString()}</span></p>
          <p><span>Capacity</span><span className="val">{velocity_stats.capacity_sats.toLocaleString()} sats</span></p>
          <p><span>Capacity (USD)</span><span className="val">${velocity_stats.capacity_usd.toLocaleString()}</span></p>
          <p><span>BTC Price</span><span className="val">${velocity_stats.btc_price_usd.toLocaleString()}</span></p>
        </>
      )}
    </div>
  );
}

export default VelocityStats;
