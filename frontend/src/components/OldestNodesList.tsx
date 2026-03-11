import { useState, useEffect } from "react";
import type { OldestNodes } from "../types";
import { fetchOldestNodes } from "../api";

function OldestNodesList() {
  const [oldest_nodes, setOldestNodes] = useState<OldestNodes[] | null>(null);

  useEffect(() => {
    fetchOldestNodes().then((data) => setOldestNodes(data));
  }, []);

  return (
    <div>
      {oldest_nodes && (
        <ul>
          {oldest_nodes.map((node) => (
            <li key={node.publicKey}>
              {node.alias} - first seen {new Date(node.firstSeen * 1000).toLocaleDateString()}: capacity{" "}
              {node.capacity.toLocaleString()} satoshis
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default OldestNodesList;
