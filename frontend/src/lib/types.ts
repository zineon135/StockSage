// Shared API types (mirror the FastAPI responses).

export interface Meta {
  source: string
  fetched_at: string
  stale: boolean
  stale_reason: string | null
}

export interface ApiErrorBody {
  code: string
  message: string
  details?: unknown
}

export type Section<T> = { data: T; meta: Meta } | { error: ApiErrorBody }

export interface Quote {
  symbol: string
  price: number
  change: number | null
  change_pct: number | null
  open: number | null
  high: number | null
  low: number | null
  prev_close: number | null
  market_time: string
}

export interface Profile {
  symbol: string
  available: boolean
  name?: string
  exchange?: string
  industry?: string
  country?: string
  currency?: string
  ipo?: string
  logo?: string | null
  weburl?: string | null
  market_cap?: number | null
  shares_outstanding?: number | null
}

export interface Metrics {
  symbol: string
  week52_high: number | null
  week52_high_date: string | null
  week52_low: number | null
  week52_low_date: string | null
  pe_ttm: number | null
  eps_ttm: number | null
  beta: number | null
  dividend_yield_pct: number | null
  avg_volume_10d: number | null
  revenue_growth_ttm_yoy_pct: number | null
  net_margin_ttm_pct: number | null
  return_52w_pct: number | null
}

export interface StockDetail {
  symbol: string
  quote: Section<Quote>
  profile: Section<Profile>
  metrics: Section<Metrics>
}

export type RangeKey = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | '5Y'

export interface Bar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  sma50?: number | null
  sma200?: number | null
}

export interface HistoryResponse {
  symbol: string
  range: RangeKey
  bars: Bar[]
  performance_pct: number | null
  provider: string
  adjusted: boolean
  earliest_available: string | null
  available_ranges: RangeKey[]
  note: string
  meta: Meta
}

export interface TechnicalSummary {
  as_of: string
  observations: number
  last_close: number
  sma50: number | null
  sma200: number | null
  price_vs_sma50_pct: number | null
  price_vs_sma200_pct: number | null
  trend_signal: string | null
  rsi14: number | null
  rsi_label: string
  volatility_30d_annualized: number | null
  volatility_label: string
  last_volume: number | null
  avg_volume_30d: number | null
  volume_vs_avg_ratio: number | null
  returns_pct: Record<string, number | null>
  max_drawdown_1y_pct: number | null
}

export interface TechnicalsResponse {
  summary: TechnicalSummary
  chart: { date: string; close: number; rsi14: number | null; volume: number; volatility30: number | null }[]
  provider: string
  meta: Meta
}

export interface Sparkline {
  symbol: string
  points: { date: string; close: number }[]
  last_session_date: string | null
  last_session_volume: number | null
  avg_volume_30d: number | null
  volume_ratio: number | null
  meta: Meta
}

export interface MoverRow {
  symbol: string
  name: string
  price: number
  change: number | null
  change_pct: number
  market_time: string
  stale: boolean
}

export interface MoversResponse {
  universe_size: number
  universe_note: string
  trending: MoverRow[]
  gainers: MoverRow[]
  losers: MoverRow[]
  breadth: { advancing: number; declining: number; unchanged: number }
  all: MoverRow[]
  errors: { symbol: string; message: string }[]
  stale: boolean
  computed_at: string
}

export interface MarketStatus {
  exchange: string
  is_open: boolean
  session: string | null
  holiday: string | null
  timezone: string | null
  as_of: string | null
}

export interface IndexItem {
  symbol: string
  name: string
  proxy_note: string
  quote?: Quote
  meta?: Meta
  error?: ApiErrorBody
}

export interface OverviewResponse {
  indices: IndexItem[]
  status: Section<MarketStatus>
}

export interface Article {
  id: string
  title: string
  description: string | null
  url: string
  publisher: string | null
  published_at: string | null
  image: string | null
  tickers: string[]
  provider: string
}

export interface NewsResponse {
  articles: Article[]
  sources: Meta[]
  warnings: string[]
}

export interface SentimentResult {
  sentiment: 'positive' | 'negative' | 'neutral'
  score: number
  company: string
  ticker: string
  reason: string
  investor_relevance: string
  model: string
}

export interface Source {
  id: string
  kind: string
  title: string
  provider: string
  publisher?: string | null
  url: string | null
  timestamp: string | null
  retrieved_at: string
  stale: boolean
}

export interface Point {
  text: string
  type: 'fact' | 'interpretation'
  source_ids: string[]
  flags: string[]
}

export interface AnalysisSection {
  summary: string
  points: Point[]
}

export interface Analysis {
  symbol: string
  company_name: string | null
  sections: Record<string, AnalysisSection>
  data_limitations: string[]
  validation_warnings: string[]
  disclaimer: string
  model: string
  sources: Source[]
  generated_at: string
}

export interface ChatAnswer {
  answer: string
  key_points: Point[]
  limitations: string[]
  suggested_followups: string[]
  validation_warnings: string[]
  disclaimer: string
  model: string
  symbol: string | null
  sources: Source[]
  generated_at: string
}

export interface Insight extends Point {
  title: string
  category: 'movement' | 'news' | 'risk' | 'pattern' | 'breadth'
  tickers: string[]
}

export interface InsightsResponse {
  insights: Insight[]
  caveats: string[]
  validation_warnings: string[]
  disclaimer: string
  model: string
  sources: Source[]
  generated_at: string
}

export interface HoldingRow {
  symbol: string
  quantity: number
  avg_cost: number
  price: number | null
  market_value: number
  cost_basis: number
  unrealized_pnl: number | null
  unrealized_pnl_pct: number | null
  allocation_pct: number
  market_time?: string
  stale?: boolean
  change_pct?: number | null
}

export interface PortfolioResponse {
  starting_cash: number
  cash: number
  holdings_value: number
  total_value: number
  invested_cost_basis: number
  unrealized_pnl: number
  realized_pnl: number
  total_return: number
  total_return_pct: number
  holdings: HoldingRow[]
  unpriced_symbols: string[]
  valued_at: string
  simulated: boolean
}

export interface Transaction {
  id: number
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: number
  fee: number
  total: number
  realized_pnl: number | null
  price_timestamp: string
  price_source: string
  executed_at: string
}

export interface Snapshot {
  taken_at: string
  total_value: number
  cash: number
  holdings_value: number
}

export interface WatchItem {
  symbol: string
  added_at: string
  quote?: Quote
  meta?: Meta
  error?: ApiErrorBody | null
}

export interface UserSettings {
  display_name: string
  default_range: Exclude<RangeKey, '1D'>
  beginner_mode: boolean
  commission: number
  show_sma: boolean
}

export interface SystemStatus {
  server_time: string
  providers: Record<'finnhub' | 'tiingo' | 'alphavantage' | 'newsapi' | 'gemini', boolean>
  ai_model: string
  disclaimer: string
  data_notes: string[]
}

// ---- Alpaca paper brokerage ----
export interface BrokerAccount {
  account_number: string | null; status: string | null; currency: string | null
  cash: number | null; equity: number | null; last_equity: number | null; buying_power: number | null
  portfolio_value: number | null; long_market_value: number | null
  trading_blocked: boolean; pattern_day_trader: boolean; environment: 'paper'
}
export interface BrokerClock { is_open: boolean | null; next_open: string | null; next_close: string | null; timestamp: string | null }
export interface BrokerStatus { configured: boolean; environment: 'paper'; account?: BrokerAccount; clock?: BrokerClock }
export interface BrokerPosition {
  symbol: string; qty: number | null; side: string | null; avg_entry_price: number | null; current_price: number | null
  market_value: number | null; cost_basis: number | null; unrealized_pl: number | null; unrealized_plpc: number | null; change_today_pct: number | null
}
export interface BrokerOrder {
  id: string; symbol: string; side: 'buy' | 'sell'; type: string; qty: number | null; filled_qty: number | null
  filled_avg_price: number | null; limit_price: number | null; time_in_force: string | null; status: string
  submitted_at: string | null; filled_at: string | null; canceled_at: string | null
}
