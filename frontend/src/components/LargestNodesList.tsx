import { useState, useEffect } from "react";
import type { LargestNode } from "../types";
import { fetchLargestNodes } from "../api";
import { satsToBtc } from "../utils";
import InfoTooltip from "./InfoTooltip";
import { SkeletonTableRows } from "./Skeleton";

function LargestNodesList({ refreshKey }: { refreshKey?: number }) {
  const [largest_nodes, setLargestNodes] = useState<LargestNode[] | null>(null);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    fetchLargestNodes().then((data) => {
      setLargestNodes(data);
      setFlash(true);
    });
  }, [refreshKey]);

  return (
    <div className={`card${flash ? " card--flash" : ""}`}>
      <h2>
        Largest Lightning Nodes
        <InfoTooltip>
          <span className="info-tooltip-title">What makes a node "largest"?</span>
          <p className="info-tooltip-body">
            Nodes are ranked by <strong>total channel capacity</strong> — the sum of all BTC locked across their open channels. More capacity means the node can route larger payments.<br /><br />
            These are the <strong>routing hubs</strong> of the Lightning Network. When you send a payment, it likely hops through one or more of these nodes.<br /><br />
            <strong>The trade-off:</strong> large hubs make the network more efficient, but also more centralised. The <strong>Pulse Score</strong> and <strong>Gini coefficient</strong> in the Network Metrics card measure how healthy this balance is.
          </p>
        </InfoTooltip>
      </h2>
      {largest_nodes ? (
        <table className="node-table">
          <thead>
            <tr>
              <th className="node-th node-th--name">Name</th>
              <th className="node-th node-th--capacity">Capacity</th>
              <th className="node-th node-th--channels">Channels</th>
            </tr>
          </thead>
          <tbody>
            {largest_nodes.slice(0, 20).map((node) => (
              <tr key={node.publicKey} className="node-row">
                <td className="node-td node-td--name">{node.alias || node.publicKey.slice(0, 12) + "…"}</td>
                <td className="node-td node-td--capacity">{satsToBtc(node.capacity)}</td>
                <td className="node-td node-td--channels">{node.channels.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <SkeletonTableRows rows={10} />
      )}
    </div>
  );
}

export default LargestNodesList;
