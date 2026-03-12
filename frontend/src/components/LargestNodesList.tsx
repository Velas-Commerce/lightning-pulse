import { useState, useEffect } from "react";
import type { LargestNode } from "../types";
import { fetchLargestNodes } from "../api";

function LargestNodesList() {
  const [largest_nodes, setLargestNodes] = useState<LargestNode[] | null>(null);

  useEffect(() => {
    fetchLargestNodes().then((data) => setLargestNodes(data));
  }, []);

  return (
    <div className="card">
      <h2>Largest Lightning Nodes</h2>
      {largest_nodes && (
        <ul>
          {largest_nodes.slice(0, 20).map((node) => (
            <li key={node.publicKey}>
              <span className="label">{node.alias || node.publicKey.slice(0, 12) + "…"}</span>
              <span className="val">{node.capacity.toLocaleString()} sats · {node.channels} ch</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default LargestNodesList;
