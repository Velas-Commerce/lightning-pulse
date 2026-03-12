import { useState, useEffect } from "react";
import type { NetworkMetrics } from "../types";
import { fetchNetworkMetrics } from "../api";

function NetworkMetricsList() {
  const [network_metrics, setNetworkMetrics] = useState<NetworkMetrics | null>(null);

  useEffect(() => {
    fetchNetworkMetrics().then((data) => setNetworkMetrics(data));
  }, []);

  return (
    <div>
      <h2>Network Metrics</h2>
      {network_metrics && (
        <>
          <p>Pulse Score: {network_metrics.pulse_score.toLocaleString()}</p>
          <p>Gini Coefficient: {network_metrics.gini_coefficient.toLocaleString()}</p>
          <p>Top 10 Centralization: {network_metrics.top10_centralization.toLocaleString()}</p>
          <p>Top 100 Centralization: {network_metrics.top100_centralization.toLocaleString()}</p>
          <p>Median Fee Rate: {network_metrics.median_fee_rate.toLocaleString()}</p>
          <p>Median Node Degree: {network_metrics.median_node_degree.toLocaleString()}</p>
          <p>Last Computed: {network_metrics.last_computed.toLocaleString()}</p>
        </>
      )}
    </div>
  );
}

export default NetworkMetricsList;
