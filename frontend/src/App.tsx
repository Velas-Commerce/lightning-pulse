import { useState, useEffect } from "react";
import "./App.css";
import type { HealthStatus } from "./types";
import { fetchHealth } from "./api";
import Header from "./components/Header";
import Footer from "./components/Footer";
import NodesPerCountryList from "./components/NodesPerCountryList";
import LargestNodesList from "./components/LargestNodesList";
import NetworkMetricsList from "./components/NetworkMetricsList";
import NetworkTopology from "./components/NetworkTopology";
import GrowthStats from "./components/GrowthStats";
import VelocityStats from "./components/VelocityStats";
import ReportCard from "./components/ReportCard";

const REFRESH_INTERVAL_MS = 60_000; // 60 seconds

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  useEffect(() => {
    fetchHealth().then((data) => setHealth(data));
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setRefreshKey((k) => k + 1);
      setLastRefreshed(new Date());
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const statusLabel = health
    ? `API ${health.status} · ${health.metrics_ready ? "live" : "loading"}`
    : undefined;

  return (
    <div>
      <Header status={statusLabel} lastRefreshed={lastRefreshed} />
      {/* Sibling of the grid, not a child of it: the grid assigns column spans by
          :nth-child, so inserting a card would shift NetworkMetricsList to
          nth-child(4), which matches no rule and collapses it to 1 of 6 columns. */}
      <div className="report-card-row">
        <ReportCard />
      </div>
      <div className="dashboard-grid">
        <GrowthStats refreshKey={refreshKey} />
        <VelocityStats refreshKey={refreshKey} />
        <NetworkMetricsList refreshKey={refreshKey} />
        <NetworkTopology refreshKey={refreshKey} />
        <NodesPerCountryList refreshKey={refreshKey} />
        <LargestNodesList refreshKey={refreshKey} />
      </div>
      <Footer />
    </div>
  );
}

export default App;
