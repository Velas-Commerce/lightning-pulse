import { useState, useEffect } from "react";
import type { BtcPrice } from "../types";
import { fetchBtcPrice } from "../api";

function MarketData() {
  const [price, setPrice] = useState<BtcPrice | null>(null);

  useEffect(() => {
    fetchBtcPrice().then((data) => setPrice(data));
  }, []);

  return (
    <div>
      <h2>Market Data</h2>
      {price && <p>$ {price.USD.toLocaleString()} USD / BTC</p>}
      {price && <p>{Math.round(100_000_000 / price.USD).toLocaleString()} SATS / USD</p>}
    </div>
  );
}

export default MarketData;
