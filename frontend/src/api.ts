const BASE_URL = "http://localhost:8000";

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

export async function fetchOldestNodes() {
  const res = await fetch(`${BASE_URL}/lightning/oldest-nodes`);
  return res.json();
}

export async function fetchGraphInfo() {
  const res = await fetch(`${BASE_URL}/node/graph-info`);
  return res.json();
}

export async function fetchNetworkMetrics() {
  const res = await fetch(`${BASE_URL}/node/network-metrics`);
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
