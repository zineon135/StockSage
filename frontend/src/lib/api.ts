import type {
  Analysis, ChatAnswer, HistoryResponse, InsightsResponse, MoversResponse, NewsResponse, OverviewResponse,
  PortfolioResponse, RangeKey, SentimentResult, Snapshot, Sparkline, StockDetail, SystemStatus, TechnicalsResponse,
  Transaction, UserSettings, WatchItem, Article, Meta, Section, MarketStatus,
  BrokerStatus, BrokerPosition, BrokerOrder,
} from './types'

export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError('Cannot reach the Stock Sage server. Is the backend running on port 8000?', 'network_error', 0)
  }
  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    // Vite proxy returns HTML/plain text when backend is down
    throw new ApiError(
      res.status >= 500 ? 'The Stock Sage server is not responding. Start the backend and try again.' : 'Unexpected server response.',
      'bad_response',
      res.status,
    )
  }
  if (!res.ok) {
    const e = (body as { error?: { code: string; message: string } })?.error
    throw new ApiError(e?.message ?? `Request failed (${res.status})`, e?.code ?? 'http_error', res.status)
  }
  if (path.startsWith('/api/market') || path.startsWith('/api/stocks') || path.startsWith('/api/watchlist') || path.startsWith('/api/portfolio')) {
    window.dispatchEvent(new CustomEvent('stocksage:data'))
  }
  return body as T
}

const post = <T>(path: string, data?: unknown) => request<T>(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined })

export const api = {
  system: () => request<SystemStatus>('/api/system/status'),
  marketStatus: () => request<Section<MarketStatus>>('/api/market/status'),
  overview: () => request<OverviewResponse>('/api/market/overview'),
  movers: () => request<MoversResponse>('/api/market/movers'),
  insights: () => request<{ data: InsightsResponse; meta: Meta }>('/api/market/insights'),

  search: (q: string) => request<{ data: { symbol: string; name: string; type: string }[]; meta: Meta }>(`/api/stocks/search?q=${encodeURIComponent(q)}`),
  stock: (s: string) => request<StockDetail>(`/api/stocks/${encodeURIComponent(s)}`),
  history: (s: string, range: Exclude<RangeKey, '1D'>) => request<HistoryResponse>(`/api/stocks/${encodeURIComponent(s)}/history?range=${range}`),
  intraday: (s: string) => request<{ data: { symbol: string; provider: string; bars: { date: string; close: number; volume: number }[] }; meta: Meta }>(`/api/stocks/${encodeURIComponent(s)}/intraday`),
  technicals: (s: string) => request<TechnicalsResponse>(`/api/stocks/${encodeURIComponent(s)}/technicals`),
  sparkline: (s: string, days = 30) => request<Sparkline>(`/api/stocks/${encodeURIComponent(s)}/sparkline?days=${days}`),

  news: (category: 'markets' | 'economy' | 'technology') => request<NewsResponse>(`/api/news?category=${category}`),
  companyNews: (s: string) => request<NewsResponse>(`/api/news/company/${encodeURIComponent(s)}`),
  sentiment: (articles: Article[]) =>
    post<{ results: Record<string, SentimentResult>; note: string }>('/api/news/sentiment', {
      articles: articles.map((a) => ({
        id: a.id, title: a.title.slice(0, 500), description: a.description?.slice(0, 1000) ?? null,
        publisher: a.publisher, published_at: a.published_at, tickers: a.tickers.slice(0, 5),
      })),
    }),

  analyze: (s: string, refresh = false) => post<{ data: Analysis; meta: Meta }>(`/api/ai/analyze/${encodeURIComponent(s)}${refresh ? '?refresh=true' : ''}`),
  chat: (question: string, symbol: string | null, history: { role: 'user' | 'assistant'; content: string }[]) =>
    post<ChatAnswer>('/api/ai/chat', { question, symbol, history }),

  watchlist: () => request<{ items: WatchItem[] }>('/api/watchlist'),
  addWatch: (symbol: string) => post<{ symbol: string; added: boolean }>('/api/watchlist', { symbol }),
  removeWatch: (symbol: string) => request<{ removed: boolean }>(`/api/watchlist/${encodeURIComponent(symbol)}`, { method: 'DELETE' }),

  portfolio: () => request<PortfolioResponse>('/api/portfolio'),
  trade: (symbol: string, side: 'BUY' | 'SELL', quantity: number) =>
    post<{ transaction: Transaction; portfolio: PortfolioResponse }>('/api/portfolio/trade', { symbol, side, quantity }),
  transactions: () => request<{ transactions: Transaction[] }>('/api/portfolio/transactions'),
  portfolioHistory: () => request<{ starting_cash: number; created_at: string; snapshots: Snapshot[]; note: string }>('/api/portfolio/history'),
  resetPortfolio: () => post<{ cash: number }>('/api/portfolio/reset'),

  settings: () => request<UserSettings>('/api/settings'),
  saveSettings: (s: Partial<UserSettings>) => request<UserSettings>('/api/settings', { method: 'PUT', body: JSON.stringify(s) }),

  // Alpaca PAPER account (virtual money through a real broker's order system)
  brokerStatus: () => request<BrokerStatus>('/api/broker/status'),
  brokerPositions: () => request<{ positions: BrokerPosition[] }>('/api/broker/positions'),
  brokerOrders: (status: 'open' | 'closed' | 'all' = 'all') => request<{ orders: BrokerOrder[] }>(`/api/broker/orders?status=${status}`),
  brokerPlaceOrder: (o: { symbol: string; side: 'buy' | 'sell'; qty: number; type: 'market' | 'limit'; limit_price?: number | null }) =>
    post<{ order: BrokerOrder; environment: 'paper' }>('/api/broker/orders', { ...o, confirm: true }),
  brokerCancelOrder: (id: string) => request<{ canceled: string }>(`/api/broker/orders/${encodeURIComponent(id)}`, { method: 'DELETE' }),
}
