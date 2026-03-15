import { useState, useEffect } from "react";
import "./App.css";
import type { HealthStatus } from "./types";
import { fetchHealth } from "./api";
import NodesPerCountryList from "./components/NodesPerCountryList";
import LargestNodesList from "./components/LargestNodesList";
import NetworkMetricsList from "./components/NetworkMetricsList";
import NetworkTopology from "./components/NetworkTopology";
import GrowthStats from "./components/GrowthStats";
import VelocityStats from "./components/VelocityStats";

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    fetchHealth().then((data) => setHealth(data));
  }, []);

  return (
    <div>
      <header className="dashboard-header">
        <h1>⚡ Lightning Pulse</h1>
        {health && (
          <p className="api-status">
            API {health.status} · metrics {health.metrics_ready ? "ready" : "loading"}
          </p>
        )}
      </header>
      <div className="dashboard-grid">
        <GrowthStats />
        <VelocityStats />
        <NetworkMetricsList />
        <NetworkTopology />
        <NodesPerCountryList />
        <LargestNodesList />
      </div>
    </div>
  );
}

export default App;
