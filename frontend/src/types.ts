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

// One daily snapshot from GET /history/lightning-stats (LightningStats + recorded_at)
export type LightningStatsHistoryEntry = LightningStats & {
  recorded_at: string;
};

// One derived daily point from GET /history/velocity
export type VelocityHistoryEntry = {
  recorded_at: string;
  velocity: number;
  capacity_sats: number;
  btc_price_usd: number;
};

export type NodesPerCountry = {
  name: Record<string, string>;
  iso: string;
  count: number;
  share: number;
  capacity: string | null;
};

export type LargestNode = {
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

// One daily snapshot from GET /history/network-metrics (NetworkMetrics + recorded_at)
export type NetworkMetricsHistoryEntry = NetworkMetrics & {
  recorded_at: string;
};

export type MonthlyVolumeEntry = {
  date: string;
  volume_usd: number;
  transactions: number;
};

export type LightningGrowthStats = {
  sources: string[];
  avg_transaction_usd: number;
  num_lightning_users: number;
  monthly_volume: MonthlyVolumeEntry[];
};

export type LiquidityVelocity = {
  velocity: number;
  monthly_volume_usd: number;
  volume_date: number;
  capacity_sats: number;
  capacity_usd: number;
  btc_price_usd: number;
};

// ── Daily report card (GET /report/daily) ─────────────────────────────────────

export type HourlyFlow = {
  hour: number;
  opens: number[]; // one entry per channel, capacity in BTC
  closes: number[];
};

export type ReportFlow = {
  opens: number;
  btc_in: number;
  closes: number; // 0 until close detection has a set to diff against
  btc_out: number;
  net_channels: number;
  net_btc: number;
  // Channel sizes in BTC, computed server-side. Median not mean — the distribution
  // is skewed roughly 4:1 — and present even on days without hourly detail.
  median_open: number;
  largest_open: number;
  hourly: HourlyFlow[] | null; // null when block times were interpolated
};

export type ReportBaseline = {
  window_days: number; // days of history held — what a trend would span
  live_days: number; // of those, how many the baseline is computed from
  opens_median: number;
  opens_mad: number;
  btc_in_median: number;
  btc_in_mad: number;
  // Zero until enough days carry close data; closes cannot be backfilled
  closes_days: number;
  closes_median: number;
  closes_mad: number;
  btc_out_median: number;
  btc_out_mad: number;
};

export type SlowIndex = {
  key: string;
  label: string;
  value: number;
  percentile: number; // position within the window, never a daily delta
  series: number[];
  as_of: string; // date the value describes; mempool-derived ones run weeks behind
  stale_days: number;
};

export type ReportVerdict = {
  headline: string;
  subline: string;
  lead_metric: string;
  deviation: number;
  // Substring of the headline to emphasise; plain text, no markup crosses the API
  highlight: string | null;
};

export type DailyReport = {
  date: string;
  weekday: string; // UTC weekday, generated server-side alongside the copy
  block_from: number; // first block of the day; the range is the real window
  block_height: number;
  flow: ReportFlow;
  baseline: ReportBaseline;
  slow: SlowIndex[];
  verdict: ReportVerdict;
  closes_available: boolean; // false until on-chain close detection lands
  coverage_note: string;
};
