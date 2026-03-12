import { useState, useEffect } from "react";
import type { LargestNode } from "../types";
import { fetchLargestNodes } from "../api";

function LargestNodesList() {
  const [largest_nodes, setLargestNodes] = useState<LargestNode[] | null>(null);

  useEffect(() => {
    fetchLargestNodes().then((data) => setLargestNodes(data));
  }, []);

  return (
    <div>
      <h2>Largest Lightning Nodes</h2>
      {largest_nodes && (
        <ul>
          {largest_nodes.map((node) => (
            <li key={node.publicKey}>
              {node.alias} — {node.capacity.toLocaleString()} sats ({node.channels} channels)
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default LargestNodesList;
