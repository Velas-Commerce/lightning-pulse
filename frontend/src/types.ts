export type HealthStatus = {
  status: string;
  metrics_ready: boolean;
};

export type BtcPrice = {
  time: number;
  USD: number;
  EUR: number;
  GBP: number;
  CAD: number;
  CHF: number;
  AUD: number;
  JPY: number;
};

export type LightningStats = {
  id: number;
  added: string;
  channel_count: number;
  node_count: number;
  total_capacity: number;
  tor_nodes: number;
  clearnet_nodes: number;
  unannounced_nodes: number;
  avg_capacity: number;
  avg_fee_rate: number;
  avg_base_fee_mtokens: number;
  med_capacity: number;
  med_fee_rate: number;
  med_base_fee_mtokens: number;
  clearnet_tor_nodes: number;
};

export type LightningStatsResponse = {
  latest: LightningStats;
};

export type NodesPerCountry = {
  name: Record<string, string>;
  iso: string;
  count: number;
  share: number;
  capacity: string | null;
};

export type OldestNodes = {
  publicKey: string;
  alias: string;
  channels: number;
  capacity: number;
  firstSeen: number;
  updatedAt: number;
  city: Record<string, string> | null;
  country: Record<string, string> | null;
};

export type GraphInfo = {
  graph_diameter: number;
  avg_out_degree: number;
  max_out_degree: number;
  num_nodes: number;
  num_channels: number;
  total_network_capacity: string;
  avg_channel_size: number;
  min_channel_size: number;
  max_channel_size: string;
  median_channel_size_sat: string;
  num_zombie_chans: string;
};

export type NetworkMetrics = {
  pulse_score: number;
  gini_coefficient: number;
  top10_centralization: number;
  top100_centralization: number;
  median_fee_rate: number;
  median_node_degree: number;
  last_computed: string;
};
