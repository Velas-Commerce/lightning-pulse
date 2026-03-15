import { useState, useEffect } from "react";
import "./App.css";
import type { HealthStatus } from "./types";
import { fetchHealth } from "./api";
import Header from "./components/Header";
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

  const statusLabel = health
    ? `API ${health.status} · ${health.metrics_ready ? "live" : "loading"}`
    : undefined;

  return (
    <div>
      <Header status={statusLabel} />
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
