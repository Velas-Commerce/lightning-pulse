import { useState, useEffect } from "react";
import type { HealthStatus, BtcPrice } from "./types";
import { fetchHealth, fetchBtcPrice } from "./api";

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [price, setPrice] = useState<BtcPrice | null>(null);

  useEffect(() => {
    Promise.all([fetchHealth(), fetchBtcPrice()]).then(([healthData, priceData]) => {
      setHealth(healthData);
      setPrice(priceData);
    });
  }, []);

  return (
    <div>
      <h1>Lightning Dashboard</h1>
      {health && (
        <p>
          API status: {health.status} - metrics ready: {String(health.metrics_ready)}
        </p>
      )}
      {price && <p>BTC price: $ {price.USD.toLocaleString()} USD</p>}
    </div>
  );
}

export default App;
