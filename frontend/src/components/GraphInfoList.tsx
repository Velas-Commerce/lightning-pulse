import { useState, useEffect } from "react";
import type { GraphInfo } from "../types";
import { fetchGraphInfo } from "../api";

function GraphInfoList() {
  const [graph_info, setGraphInfo] = useState<GraphInfo | null>(null);

  useEffect(() => {
    fetchGraphInfo().then((data) => setGraphInfo(data));
  }, []);

  return (
    <div className="card">
      <h2>Graph Info</h2>
      {graph_info && (
        <>
          <p><span>Nodes</span><span className="val">{graph_info.num_nodes.toLocaleString()}</span></p>
          <p><span>Channels</span><span className="val">{graph_info.num_channels.toLocaleString()}</span></p>
          <p><span>Graph Diameter</span><span className="val">{graph_info.graph_diameter.toLocaleString()}</span></p>
          <p><span>Avg Channel Size</span><span className="val">{Math.round(graph_info.avg_channel_size).toLocaleString()} sats</span></p>
          <p><span>Total Capacity</span><span className="val">{graph_info.total_network_capacity}</span></p>
        </>
      )}
    </div>
  );
}

export default GraphInfoList;
