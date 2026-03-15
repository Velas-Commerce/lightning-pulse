import { useState, useEffect } from "react";
import type { LargestNode } from "../types";
import { fetchLargestNodes } from "../api";
import { satsToBtc } from "../utils";

function LargestNodesList() {
  const [largest_nodes, setLargestNodes] = useState<LargestNode[] | null>(null);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    fetchLargestNodes().then((data) => {
      setLargestNodes(data);
      setFlash(true);
    });
  }, []);

  return (
    <div className={`card${flash ? " card--flash" : ""}`}>
      <h2>Largest Lightning Nodes</h2>
      {largest_nodes && (
        <ul>
          {largest_nodes.slice(0, 20).map((node) => (
            <li key={node.publicKey}>
              <span className="label">{node.alias || node.publicKey.slice(0, 12) + "…"}</span>
              <span className="val">{satsToBtc(node.capacity)} · {node.channels} ch</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default LargestNodesList;
