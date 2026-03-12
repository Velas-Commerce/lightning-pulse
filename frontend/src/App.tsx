import { useState, useEffect } from "react";
import type { HealthStatus } from "./types";
import { fetchHealth } from "./api";
import MarketData from "./components/MarketData";
import LightningStats from "./components/LightningStats";
import NodesPerCountryList from "./components/NodesPerCountryList";
import OldestNodesList from "./components/OldestNodesList";
import GraphInfoList from "./components/GraphInfoList";
import NetworkMetricsList from "./components/NetworkMetricsList";

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    fetchHealth().then((data) => setHealth(data));
  }, []);

  return (
    <div>
      <h1>Lightning Pulse</h1>
      {health && (
        <p>
          API status: {health.status} - metrics ready: {String(health.metrics_ready)}
        </p>
      )}
      <MarketData />
      <NetworkMetricsList />
      <LightningStats />
      <GraphInfoList />
      <NodesPerCountryList />
      <OldestNodesList />
    </div>
  );
}

export default App;
