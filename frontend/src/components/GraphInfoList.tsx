import { useState, useEffect } from "react";
import type { GraphInfo } from "../types";
import { fetchGraphInfo } from "../api";

function GraphInfoList() {
  const [graph_info, setGraphInfo] = useState<GraphInfo | null>(null);

  useEffect(() => {
    fetchGraphInfo().then((data) => setGraphInfo(data));
  }, []);

  return (
    <div>
      <h2>Graph Info</h2>
      {graph_info && (
        <>
        <p>Graph Diameter: {graph_info.graph_diameter.toLocaleString()}</p>
        <p>Average Channel Size: {Math.round(graph_info.avg_channel_size).toLocaleString()} SATS</p>
      </>
      )}
    </div>
  );
}

export default GraphInfoList;