const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}

export async function fetchBtcPrice() {
  const res = await fetch(`${BASE_URL}/btc-price`);
  return res.json();
}

export async function fetchLightningStats() {
  const res = await fetch(`${BASE_URL}/lightning/stats`);
  return res.json();
}

export async function fetchNodesPerCountry() {
  const res = await fetch(`${BASE_URL}/lightning/nodes-per-country`);
  return res.json();
}

export async function fetchLargestNodes() {
  const res = await fetch(`${BASE_URL}/lightning/largest-nodes`);
  return res.json();
}

// Throws on non-OK — /node/* returns 503 while the LND node is unreachable
export async function fetchGraphInfo() {
  const res = await fetch(`${BASE_URL}/node/graph-info`);
  if (!res.ok) throw new Error(`LND unavailable (${res.status})`);
  return res.json();
}

// Throws on non-OK — 503 until the first metrics computation finishes
export async function fetchNetworkMetrics() {
  const res = await fetch(`${BASE_URL}/node/network-metrics`);
  if (!res.ok) throw new Error(`Network metrics unavailable (${res.status})`);
  return res.json();
}

export async function fetchGrowthStats() {
  const res = await fetch(`${BASE_URL}/lightning/growth-stats`);
  return res.json();
}

export async function fetchVelocityStats() {
  const res = await fetch(`${BASE_URL}/lightning/velocity`);
  return res.json();
}

// Throws on non-OK — /history/* returns 503 when MongoDB is not configured
export async function fetchLightningStatsHistory(days = 90) {
  const res = await fetch(`${BASE_URL}/history/lightning-stats?days=${days}`);
  if (!res.ok) throw new Error(`History unavailable (${res.status})`);
  return res.json();
}

// Derived velocity series (capacity snapshots × historical BTC price); same 503 rule
export async function fetchVelocityHistory(days = 90) {
  const res = await fetch(`${BASE_URL}/history/velocity?days=${days}`);
  if (!res.ok) throw new Error(`History unavailable (${res.status})`);
  return res.json();
}

// Daily network-metrics snapshots (pulse, gini, centralization, fees); same 503 rule
export async function fetchNetworkMetricsHistory(days = 90) {
  const res = await fetch(`${BASE_URL}/history/network-metrics?days=${days}`);
  if (!res.ok) throw new Error(`History unavailable (${res.status})`);
  return res.json();
}
