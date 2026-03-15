import { useState, useEffect } from "react";
import type { LightningStatsResponse, GraphInfo } from "../types";
import { fetchLightningStats, fetchGraphInfo } from "../api";
import { satsToBtc } from "../utils";

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

function NetworkTopology() {
  const [ls, setLs] = useState<LightningStatsResponse | null>(null);
  const [gi, setGi] = useState<GraphInfo | null>(null);

  useEffect(() => {
    fetchLightningStats().then(setLs);
    fetchGraphInfo().then(setGi);
  }, []);

  const s = ls?.latest;

  return (
    <div className="card topology-card">
      <h2>Network Topology</h2>

      {s && gi && (
        <>
          {/* ── Explainer ─────────────────────────────────── */}
          <p className="nt-note">
            A Lightning node builds its graph from gossip messages — it only sees
            channels that have been announced and relayed to it. Mempool.space may
            aggregate many crawlers, giving broader coverage. The gap shows
            our node's network visibility.
          </p>

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
              </span>
            </div>
          </div>

          {/* ── LND-only metrics ──────────────────────────── */}
          <p className="section-label">LND node only</p>
          <p><span>Graph Diameter</span><span className="val">{gi.graph_diameter}</span></p>
          <p><span>Avg Node Degree</span><span className="val">{gi.avg_out_degree.toLocaleString()}</span></p>
          <p><span>Max Node Degree</span><span className="val">{gi.max_out_degree.toLocaleString()}</span></p>
          <p><span>Median Channel</span><span className="val">{parseInt(gi.median_channel_size_sat, 10).toLocaleString()} sats</span></p>
          <p><span>Zombie Channels</span><span className="val">{gi.num_zombie_chans}</span></p>

          {/* ── Mempool-only metrics ──────────────────────── */}
          <p className="section-label">Mempool.space only</p>
          <p><span>Avg Fee Rate</span><span className="val">{s.avg_fee_rate.toLocaleString()} ppm</span></p>
          <p><span>Med Fee Rate</span><span className="val">{s.med_fee_rate.toLocaleString()} ppm</span></p>
          <p><span>Med Capacity</span><span className="val">{s.med_capacity.toLocaleString()} sats</span></p>
          <p><span>Tor Nodes</span><span className="val">{s.tor_nodes.toLocaleString()}</span></p>
          <p><span>Clearnet Nodes</span><span className="val">{s.clearnet_nodes.toLocaleString()}</span></p>
          <p><span>Unannounced</span><span className="val">{s.unannounced_nodes.toLocaleString()}</span></p>
        </>
      )}
    </div>
  );
}

export default NetworkTopology;
