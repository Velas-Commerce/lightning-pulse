import { useState, useEffect } from "react";
import type { NetworkMetrics } from "../types";
import { fetchNetworkMetrics } from "../api";

function NetworkMetricsList() {
  const [network_metrics, setNetworkMetrics] = useState<NetworkMetrics | null>(null);

  useEffect(() => {
    fetchNetworkMetrics().then((data) => setNetworkMetrics(data));
  }, []);

  return (
    <div className="card">
      <h2>Network Metrics</h2>
      {network_metrics && (
        <>
          <p><span>Pulse Score</span><span className="val">{network_metrics.pulse_score.toLocaleString()}</span></p>
          <p><span>Gini Coefficient</span><span className="val">{network_metrics.gini_coefficient.toLocaleString()}</span></p>
          <p><span>Top 10 Centralization</span><span className="val">{network_metrics.top10_centralization.toLocaleString()}</span></p>
          <p><span>Top 100 Centralization</span><span className="val">{network_metrics.top100_centralization.toLocaleString()}</span></p>
          <p><span>Median Fee Rate</span><span className="val">{network_metrics.median_fee_rate.toLocaleString()} ppm</span></p>
          <p><span>Median Node Degree</span><span className="val">{network_metrics.median_node_degree.toLocaleString()}</span></p>
          <p><span>Last Computed</span><span className="val">{network_metrics.last_computed}</span></p>
        </>
      )}
    </div>
  );
}

export default NetworkMetricsList;
