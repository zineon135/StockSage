export interface GlossaryEntry {
  term: string
  short: string // one-line tooltip
  long: string // Learning Center explanation
  example?: string
  category: 'Basics' | 'Valuation' | 'Technical' | 'Risk' | 'Portfolio' | 'Markets'
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  market_cap: {
    term: 'Market Capitalization',
    category: 'Valuation',
    short: 'Total value of all a company’s shares: share price × shares outstanding.',
    long: 'Market cap tells you how big a company is in the eyes of the stock market. It changes every time the share price changes. Companies are often grouped as large-cap (over $10B), mid-cap ($2B–$10B) and small-cap (under $2B). Smaller companies often move more sharply in price.',
    example: 'A company with 1 billion shares trading at $50 has a market cap of $50 billion.',
  },
  pe_ratio: {
    term: 'P/E Ratio (Price-to-Earnings)',
    category: 'Valuation',
    short: 'Share price divided by earnings per share — how much investors pay for $1 of profit.',
    long: 'The P/E ratio compares a company’s share price with its profit per share over the last 12 months (TTM). A high P/E can mean investors expect strong growth; a low P/E can mean the market is pessimistic or the company is undervalued. It is most useful when comparing similar companies. It is not meaningful when a company has no profits.',
    example: 'A $100 stock with $5 of earnings per share has a P/E of 20.',
  },
  eps: {
    term: 'EPS (Earnings per Share)',
    category: 'Valuation',
    short: 'Company profit divided by the number of shares.',
    long: 'Earnings per share shows how much profit is attributable to each share. TTM means “trailing twelve months” — the most recent four quarters.',
  },
  rsi: {
    term: 'RSI (Relative Strength Index)',
    category: 'Technical',
    short: 'A 0–100 momentum gauge of recent gains vs losses (14 days). Above 70 = “overbought”, below 30 = “oversold”.',
    long: 'RSI compares the size of recent up-days with recent down-days. Readings above 70 suggest the stock has risen quickly and readings below 30 suggest it has fallen quickly. These zones do NOT mean the price must reverse — strong trends can keep RSI high or low for a long time. RSI describes past price behaviour only.',
    example: 'An RSI of 78 means recent gains have been much larger than recent losses.',
  },
  moving_average: {
    term: 'Moving Average',
    category: 'Technical',
    short: 'The average closing price over a recent window, recalculated each day to smooth out noise.',
    long: 'A moving average smooths daily price swings so you can see the general direction. The 50-day average reflects the medium-term trend; the 200-day average reflects the long-term trend. When the price is above its 200-day average, the stock has been in a longer-term uptrend. When the 50-day crosses above the 200-day, some traders call it a “golden cross”; the opposite is a “death cross”. These are descriptions of history, not predictions.',
    example: 'If the last 50 closing prices average $120, the 50-day moving average is $120.',
  },
  sma50: {
    term: '50-Day Moving Average',
    category: 'Technical',
    short: 'Average closing price over the last 50 trading days (about 2½ months).',
    long: 'Used to describe the medium-term trend.',
  },
  sma200: {
    term: '200-Day Moving Average',
    category: 'Technical',
    short: 'Average closing price over the last 200 trading days (about 10 months).',
    long: 'Used to describe the long-term trend.',
  },
  volatility: {
    term: 'Volatility',
    category: 'Risk',
    short: 'How much a price swings. Stock Sage shows 30-day annualized volatility of daily returns.',
    long: 'Volatility measures how widely a stock’s price moves around. Higher volatility means larger swings — up and down. Stock Sage calculates historical volatility as the standard deviation of daily log returns over the last 30 trading days, scaled to a yearly figure (× √252). As a rough guide, broad-market index funds are often around 15–20% per year, while individual tech stocks are frequently 30–60%.',
    example: '40% annualized volatility means daily moves of roughly ±2.5% are common.',
  },
  volume: {
    term: 'Trading Volume',
    category: 'Basics',
    short: 'Number of shares traded during a period. Unusually high volume shows heightened interest.',
    long: 'Volume counts how many shares changed hands. A price move on high volume means many investors took part; a move on low volume involved fewer participants. Stock Sage compares the latest session’s volume with the 30-day average to spot unusual activity.',
  },
  bull_market: {
    term: 'Bull Market',
    category: 'Markets',
    short: 'A period of generally rising prices — commonly defined as a 20%+ rise from a recent low.',
    long: 'Bull markets are periods when prices broadly rise and investor confidence is high. They can last for years, but they always include pullbacks along the way.',
  },
  bear_market: {
    term: 'Bear Market',
    category: 'Markets',
    short: 'A period of generally falling prices — commonly defined as a 20%+ decline from a recent high.',
    long: 'Bear markets are periods of widespread decline and pessimism. Historically they have been shorter than bull markets on average, but they can be painful and unpredictable.',
  },
  dividend: {
    term: 'Dividend',
    category: 'Basics',
    short: 'Cash a company pays to shareholders out of its profits, usually quarterly.',
    long: 'Some companies share profits with investors as dividends. Dividend yield is the yearly dividend divided by the share price. A very high yield can be a warning sign if the share price has fallen sharply or the dividend may be cut.',
    example: 'A $100 stock paying $3 per year has a 3% dividend yield.',
  },
  diversification: {
    term: 'Diversification',
    category: 'Portfolio',
    short: 'Spreading money across many investments so one bad outcome hurts less.',
    long: 'Diversification means not putting all your eggs in one basket. Owning companies in different industries, sizes and countries reduces the impact of any single company performing badly. It cannot eliminate market-wide risk.',
  },
  risk_tolerance: {
    term: 'Risk Tolerance',
    category: 'Portfolio',
    short: 'How much ups and downs you can handle, financially and emotionally.',
    long: 'Risk tolerance depends on your goals, time horizon and comfort with losses. Someone investing for 30 years can often ride out more volatility than someone who needs the money next year. Paper trading is a safe way to learn how you react to losses.',
  },
  week52: {
    term: '52-Week Range',
    category: 'Basics',
    short: 'The lowest and highest prices over the past year.',
    long: 'Shows where today’s price sits relative to the past year’s trading range.',
  },
  beta: {
    term: 'Beta',
    category: 'Risk',
    short: 'How much a stock has historically moved relative to the overall market (1.0 = same as market).',
    long: 'A beta above 1 means the stock has tended to move more than the market; below 1 means less. It is based on history and can change.',
  },
  prev_close: {
    term: 'Previous Close',
    category: 'Basics',
    short: 'The final price at the end of the previous trading session. Daily change is measured from here.',
    long: 'The daily change and percent change compare the latest price with the previous close.',
  },
  unrealized: {
    term: 'Unrealized Gain/Loss',
    category: 'Portfolio',
    short: 'Profit or loss on shares you still hold — it only becomes “real” when you sell.',
    long: 'Unrealized P&L = (current price − average cost) × shares held.',
  },
  realized: {
    term: 'Realized Gain/Loss',
    category: 'Portfolio',
    short: 'Profit or loss locked in by selling shares.',
    long: 'Realized P&L = (sale price − average cost) × shares sold − fees.',
  },
  cost_basis: {
    term: 'Average Cost (Cost Basis)',
    category: 'Portfolio',
    short: 'The average price you paid per share, including fees.',
    long: 'When you buy the same stock several times, Stock Sage uses the weighted average of your purchase prices.',
  },
  index_proxy: {
    term: 'Index ETF Proxy',
    category: 'Markets',
    short: 'An exchange-traded fund that tracks an index. Shown because free data plans don’t include index levels.',
    long: 'SPY tracks the S&P 500, QQQ tracks the NASDAQ-100, DIA tracks the Dow Jones Industrial Average and IWM tracks the Russell 2000. Their percentage moves closely follow the index, but their prices are not the index level.',
  },
  sentiment: {
    term: 'News Sentiment',
    category: 'Markets',
    short: 'Whether a headline’s tone is positive, negative or neutral for a company. It is not a price forecast.',
    long: 'Stock Sage uses AI to classify the tone of headlines and summaries. Positive news does not guarantee a price rise — prices often already reflect expectations, and many other factors matter.',
  },
  drawdown: {
    term: 'Max Drawdown',
    category: 'Risk',
    short: 'The largest peak-to-trough fall over a period.',
    long: 'Drawdown shows the worst decline an investor would have experienced from a previous high.',
  },
  paper_trading: {
    term: 'Paper Trading',
    category: 'Portfolio',
    short: 'Practice trading with virtual money. No real orders are ever placed.',
    long: 'Paper trading lets you test ideas and learn how markets behave without risking real money. Simulated fills use the latest available quote and ignore real-world factors like bid/ask spreads and slippage.',
  },
}

export type GlossaryKey = keyof typeof GLOSSARY
