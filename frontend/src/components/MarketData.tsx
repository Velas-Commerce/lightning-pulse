import { useState, useEffect } from "react";
import type { BtcPrice } from "../types";
import { fetchBtcPrice } from "../api";

function MarketData() {
  const [price, setPrice] = useState<BtcPrice | null>(null);

  useEffect(() => {
    fetchBtcPrice().then((data) => setPrice(data));
  }, []);

  return (
    <div className="card">
      <h2>Market Data</h2>
      {price && (
        <>
          <p><span>BTC Price</span><span className="val">${price.USD.toLocaleString()} USD</span></p>
          <p><span>Sats per Dollar</span><span className="val">{Math.round(100_000_000 / price.USD).toLocaleString()} sats</span></p>
        </>
      )}
    </div>
  );
}

export default MarketData;
