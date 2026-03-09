const BASE_URL = "http://localhost:8000";

export async function fetchHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}

export async function fetchBtcPrice() {
  const res = await fetch(`${BASE_URL}/btc-price`);
  return res.json();
}
