import { useState, useEffect } from "react";
import type { LightningStatsResponse, GraphInfo } from "../types";
import { fetchLightningStats, fetchGraphInfo } from "../api";
import { satsToBtc } from "../utils";
import InfoTooltip from "./InfoTooltip";
import { SkeletonStatRow } from "./Skeleton";

// Delta badge: shows what % of the mempool figure your LND node can see.
function Delta({ lnd, mempool }: { lnd: number; mempool: number }) {
  if (!mempool) return null;
  const pct = (lnd / mempool) * 100;
  const cls =
    pct >= 97 ? "nt-delta nt-delta-high" :
    pct >= 90 ? "nt-delta nt-delta-mid"  :
                "nt-delta nt-delta-low";
  return <span className={cls}>{pct.toFixed(0)}%</span>;
}

function NetworkTopology({ refreshKey }: { refreshKey?: number }) {
  const [ls, setLs] = useState<LightningStatsResponse | null>(null);
  const [gi, setGi] = useState<GraphInfo | null>(null);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    fetchLightningStats().then(setLs);
    fetchGraphInfo().then((data) => {
      setGi(data);
      setFlash(true);
    });
  }, [refreshKey]);

  const s = ls?.latest;

  return (
    <div className={`card topology-card${flash ? " card--flash" : ""}`}>
      <h2>
        Network Topology
        <InfoTooltip>
          <span className="info-tooltip-title">Why do the numbers differ?</span>
          <p className="info-tooltip-body">
            A Lightning node builds its graph from <strong>gossip messages</strong> — it only
            sees channels that have been announced and relayed to it.
            <br /><br />
            <strong>Mempool.space</strong> aggregates data from many crawlers across the
            network, giving broader coverage than any single node.
            <br /><br />
            The <strong>% gap</strong> shown next to each figure reveals our node's
            network visibility — how much of the total graph we can see from our vantage point.
          </p>
        </InfoTooltip>
      </h2>

      {s && gi ? (
        <>
          {/* ── Comparison table ──────────────────────────── */}
          <div className="nt-compare-table">
            {/* Source column headers */}
            <div className="nt-source-row">
              <span />
              <span className="nt-source-label">LND Node</span>
              <span className="nt-source-label">Mempool.space</span>
            </div>

            <div className="nt-compare-row">
              <span className="nt-row-label">Nodes</span>
              <span className="nt-row-val">{gi.num_nodes.toLocaleString()}</span>
              <span className="nt-row-val nt-row-val--right">
                {s.node_count.toLocaleString()}
                <Delta lnd={gi.num_nodes} mempool={s.node_count} />
              </span>
            </div>

            <div className="nt-compare-row">
              <span className="nt-row-label">Channels</span>
              <span className="nt-row-val">{gi.num_channels.toLocaleString()}</span>
              <span className="nt-row-val nt-row-val--right">
                {s.channel_count.toLocaleString()}
                <Delta lnd={gi.num_channels} mempool={s.channel_count} />
              </span>
            </div>

            <div className="nt-compare-row">
              <span className="nt-row-label">Avg Channel</span>
              <span className="nt-row-val">{Math.round(gi.avg_channel_size).toLocaleString()} sats</span>
              <span className="nt-row-val nt-row-val--right">
                {s.avg_capacity.toLocaleString()} sats
                <Delta lnd={gi.avg_channel_size} mempool={s.avg_capacity} />
              </span>
            </div>

            <div className="nt-compare-row">
              <span className="nt-row-label">Total Capacity</span>
              <span className="nt-row-val">{satsToBtc(parseInt(gi.total_network_capacity, 10))}</span>
              <span className="nt-row-val nt-row-val--right">
                {satsToBtc(s.total_capacity)}
                <Delta lnd={parseInt(gi.total_network_capacity, 10)} mempool={s.total_capacity} />
              </span>
            </div>
          </div>

          {/* ── LND-only metrics ──────────────────────────── */}
          <p className="section-label">
            LND node only
            <InfoTooltip>
              <span className="info-tooltip-title">LND Node Metrics</span>
              <p className="info-tooltip-body">
                <strong>Graph Diameter</strong> — the longest shortest path between any two nodes. A smaller diameter means payments can reach any destination in fewer hops.<br /><br />
                <strong>Avg / Max Node Degree</strong> — how many channels a node has on average vs. the most connected node. Higher degree = better routing options.<br /><br />
                <strong>Median Channel Size</strong> — the middle value of all channel capacities. Useful for understanding typical liquidity available per channel.<br /><br />
                <strong>Zombie Channels</strong> — channels cached in LND's local graph that haven't broadcast a gossip update in 2+ weeks. Unlike active channels, these accumulate over the node's lifetime and are never automatically deleted — making the zombie count a proxy for the total historical scale of Lightning Network activity your node has witnessed.
              </p>
            </InfoTooltip>
          </p>
          <p><span>Graph Diameter</span><span className="val">{gi.graph_diameter}</span></p>
          <p><span>Avg Node Degree</span><span className="val">{gi.avg_out_degree.toLocaleString()}</span></p>
          <p><span>Max Node Degree</span><span className="val">{gi.max_out_degree.toLocaleString()}</span></p>
          <p><span>Median Channel</span><span className="val">{parseInt(gi.median_channel_size_sat, 10).toLocaleString()} sats</span></p>
          <p><span>Zombie Channels</span><span className="val">{Number(gi.num_zombie_chans).toLocaleString()}</span></p>

          {/* ── Mempool-only metrics ──────────────────────── */}
          <p className="section-label">
            Mempool.space only
            <InfoTooltip>
              <span className="info-tooltip-title">Mempool.space Metrics</span>
              <p className="info-tooltip-body">
                <strong>Avg / Med Fee Rate</strong> — routing fees in parts-per-million (ppm). A fee of 1,000 ppm means 0.1% of the payment amount. Median is more representative than average as it ignores outliers.<br /><br />
                <strong>Med Capacity</strong> — median channel size across the network. Larger channels can route bigger payments without needing to split them.<br /><br />
                <strong>Tor Nodes</strong> — nodes using the Tor network for privacy. Higher Tor usage reflects the network's censorship-resistance.<br /><br />
                <strong>Clearnet Nodes</strong> — nodes with public IP addresses, generally faster and more reliable for routing.<br /><br />
                <strong>Unannounced</strong> — private nodes not broadcasting their existence, used for direct payments rather than routing.
              </p>
            </InfoTooltip>
          </p>
          <p><span>Avg Fee Rate</span><span className="val">{s.avg_fee_rate.toLocaleString()} ppm</span></p>
          <p><span>Med Fee Rate</span><span className="val">{s.med_fee_rate.toLocaleString()} ppm</span></p>
          <p><span>Med Capacity</span><span className="val">{s.med_capacity.toLocaleString()} sats</span></p>
          <p><span>Tor Nodes</span><span className="val">{s.tor_nodes.toLocaleString()}</span></p>
          <p><span>Clearnet Nodes</span><span className="val">{s.clearnet_nodes.toLocaleString()}</span></p>
          <p><span>Unannounced</span><span className="val">{s.unannounced_nodes.toLocaleString()}</span></p>
        </>
      ) : (
        <>
          <SkeletonStatRow /><SkeletonStatRow /><SkeletonStatRow /><SkeletonStatRow />
          <SkeletonStatRow /><SkeletonStatRow /><SkeletonStatRow /><SkeletonStatRow />
          <SkeletonStatRow /><SkeletonStatRow /><SkeletonStatRow />
        </>
      )}
    </div>
  );
}

export default NetworkTopology;
