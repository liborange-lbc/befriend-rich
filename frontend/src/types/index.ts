export interface Fund {
  id: number;
  code: string;
  name: string;
  currency: string;
  data_source: string;
  fee_rate: number;
  management_fee: number | null;
  custody_fee: number | null;
  service_fee: number | null;
  is_active: boolean;
}

export interface ClassModel {
  id: number;
  name: string;
  description: string;
}

export interface ClassCategory {
  id: number;
  model_id: number;
  parent_id: number | null;
  name: string;
  level: number;
  sort_order: number;
  children?: ClassCategory[];
}

export interface FundClassMap {
  id: number;
  fund_id: number;
  category_id: number;
  model_id: number;
}

export interface PortfolioRecord {
  id: number;
  fund_id: number;
  fund_code: string;
  fund_name: string;
  channel: string;
  record_date: string;
  amount: number;
  amount_cny: number;
  profit: number | null;
}

export interface PortfolioSnapshot {
  id: number;
  snapshot_date: string;
  total_amount_cny: number;
  model_breakdown: string;
}

export interface FundDailyPrice {
  id: number;
  fund_id: number;
  date: string;
  close_price: number;
  ma_30: number | null;
  ma_60: number | null;
  ma_90: number | null;
  ma_120: number | null;
  ma_180: number | null;
  ma_250: number | null;
  ma_360: number | null;
  dev_30: number | null;
  dev_60: number | null;
  dev_90: number | null;
  dev_120: number | null;
  dev_180: number | null;
  dev_250: number | null;
  dev_360: number | null;
}

// === 均线择时相关类型 ===

export interface MaTimingLatest {
  date: string;
  close_price: number;
  ma_250: number | null;
  dev_250: number | null;
  status: 'buy' | 'hold' | 'sell' | 'unknown';
  status_label: string;
  color: string;
}

export interface MaTimingHistoryItem {
  date: string;
  close_price: number;
  ma_250: number | null;
  dev_250: number | null;
}

export interface MaTimingData {
  fund_id: number;
  fund_name: string;
  fund_code: string;
  latest: MaTimingLatest | null;
  history: MaTimingHistoryItem[];
}

export interface Strategy {
  id: number;
  name: string;
  fund_id: number | null;
  type: string;
  config: string;
  alert_enabled: boolean;
  alert_conditions: string;
  is_active: boolean;
}

export interface BacktestResult {
  id: number;
  strategy_id: number;
  fund_id: number;
  start_date: string;
  end_date: string;
  total_return: number | null;
  annual_return: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  volatility: number | null;
  win_rate: number | null;
  profit_loss_ratio: number | null;
  trade_log: string;
  equity_curve: string;
}

export interface DeviationSummary {
  fund_id: number;
  fund_name: string;
  fund_code: string;
  date: string;
  close_price: number;
  dev_30: number | null;
  dev_60: number | null;
  dev_90: number | null;
  dev_120: number | null;
  dev_180: number | null;
  dev_360: number | null;
}

export interface DashboardOverview {
  total_amount_cny: number;
  change_amount: number;
  change_pct: number;
  latest_date: string | null;
  usd_cny_rate: number;
  hkd_cny_rate: number;
}

export interface ExchangeRateRecord {
  date: string;
  rate: number;
}

export interface FundQuote {
  fund_id: number;
  code: string;
  name: string;
  close_price: number;
  change_pct: number;
  date: string;
}

export interface AlertLogItem {
  id: number;
  fund_name: string;
  triggered_at: string;
  condition_desc: string;
  current_values: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
  meta: Record<string, unknown> | null;
}

// === 资产导入相关类型 ===

export interface ImportResult {
  total_items: number;
  matched_funds: number;
  new_funds_created: number;
  records_imported: number;
  classification_results: {
    classified: number;
    models_covered: number;
  };
  snapshot_generated: boolean;
  import_log_id: number;
}

export interface EmailPullResult {
  email_found: boolean;
  statement_date: string | null;
  total_items: number;
  matched_funds: number;
  new_funds_created: number;
  records_imported: number;
  import_log_id: number;
}

export interface ImportLog {
  id: number;
  import_date: string;
  source: string;
  file_name: string;
  record_count: number;
  new_funds_count: number;
  status: string;
  error_message: string | null;
  weekly_investment_total: number | null;
  created_at: string;
}

export interface ImportRecord {
  id: number;
  fund_id: number;
  fund_code: string;
  fund_name: string;
  channel: string;
  record_date: string;
  amount: number;
  amount_cny: number;
  profit: number;
  currency: string;
  weekly_investment: number | null;
}

export interface GroupedRecordResult {
  key: Record<string, string>;
  total_amount: number;
  total_amount_cny: number;
  total_profit: number;
  count: number;
  records: ImportRecord[];
}

export interface GroupDimension {
  key: string;
  label: string;
  type: 'date' | 'enum' | 'classification';
}

export interface RecordSummary {
  total_amount_cny: number;
  total_profit: number;
  record_count: number;
}

// === 基金透视相关类型 ===

export interface FundHolding {
  id: number;
  fund_id: number;
  fund_code: string | null;
  fund_name: string | null;
  quarter: string;
  stock_code: string;
  stock_name: string;
  holding_ratio: number | null;
  holding_shares: number | null;
  holding_value: number | null;
  holding_amount: number | null;
  disclosure_date: string | null;
}

export interface StockExposure {
  stock_code: string;
  stock_name: string;
  total_exposure_cny: number;
  funds: {
    fund_id: number;
    fund_name: string;
    amount_cny: number;
    holding_ratio: number;
    exposure_cny: number;
  }[];
}

// === 价值大师相关类型 ===

export interface GuruInfo {
  id: number;
  name: string;
  name_en: string | null;
  slug: string;
  category: string | null;
  num_holdings: number;
  num_trades: number;
}

export interface GuruDetailInfo extends GuruInfo {
  description: string | null;
}

export interface GuruListResult {
  gurus: GuruInfo[];
  total: number;
}

export interface GuruHoldingItem {
  id: number;
  stock_code: string | null;
  stock_name: string | null;
  position_change: string | null;
  trade_impact_pct: string | null;
  shares: string | null;
  value: string | null;
  weight_pct: string | null;
  ownership_pct: string | null;
  sector: string | null;
  market_cap: string | null;
  return_3m_pct: string | null;
  return_ytd_pct: string | null;
}

export interface GuruTradeItem {
  id: number;
  stock_code: string | null;
  stock_name: string | null;
  action: string | null;
  shares_changed: string | null;
  price: string | null;
  value: string | null;
  trade_date: string | null;
  report_date: string | null;
  current_shares: string | null;
}

export interface GuruStockItem {
  id: number;
  code: string | null;
  name: string | null;
  market: string | null;
  sector: string | null;
  guru_count: number;
}

export interface GuruOverviewStats {
  total_gurus: number;
  total_holdings: number;
  total_stocks: number;
  top_stocks: GuruStockItem[];
}

export interface GuruSectorStat {
  sector: string;
  count: number;
}

export interface GuruSearchResult {
  gurus: GuruInfo[];
  stocks: GuruStockItem[];
}

export interface AggregatedHolding {
  stock_code: string;
  stock_name: string;
  total_holding_value: number;
  total_holding_ratio: number;
  total_holding_amount: number;
  fund_count: number;
  funds: {
    fund_id: number;
    fund_name: string;
    fund_code: string;
    holding_ratio: number | null;
    holding_value: number | null;
    holding_amount: number | null;
    quarter: string;
  }[];
}
