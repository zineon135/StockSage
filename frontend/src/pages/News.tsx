import { useState } from 'react'
import { Newspaper, Info } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useApp } from '../lib/AppContext'
import { dateTime } from '../lib/format'
import { Card, CardHeader, PageHeader, Segmented, Skeleton } from '../components/ui/primitives'
import { EmptyState, ErrorState } from '../components/ui/states'
import { SearchBox } from '../components/layout/SearchBox'
import { NewsItem, SentimentButton, SentimentSummary, useSentiment } from '../components/stock/NewsList'

type Cat = 'markets' | 'economy' | 'technology' | 'company'

export default function News() {
  const [cat, setCat] = useState<Cat>('markets')
  const [ticker, setTicker] = useState('NVDA')
  const { system } = useApp()
  const { data, error, loading, reload } = useApi(
    () => (cat === 'company' ? api.companyNews(ticker) : api.news(cat)), [cat, ticker],
  )
  const sent = useSentiment()
  const articles = data?.articles ?? []

  return (
    <div className="space-y-5">
      <PageHeader title="Market News" subtitle="Financial headlines from NewsAPI and Finnhub, with optional AI sentiment classification." />
      <div className="flex flex-wrap items-center gap-3">
        <Segmented size="md" value={cat} onChange={setCat} options={[
          { value: 'markets', label: 'Markets' }, { value: 'economy', label: 'Economy' },
          { value: 'technology', label: 'Technology' }, { value: 'company', label: 'By company' },
        ]} />
        {cat === 'company' && (
          <div className="flex items-center gap-2">
            <SearchBox className="w-72" placeholder="Company or ticker…" onPick={setTicker} />
            <span className="num rounded-lg border border-line bg-panel-2 px-2 py-1 text-xs font-semibold text-ink">{ticker}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
        <Card className="overflow-hidden">
          <CardHeader
            title={cat === 'company' ? `${ticker} headlines` : `${cat[0].toUpperCase()}${cat.slice(1)} headlines`}
            icon={<Newspaper size={15} />}
            subtitle={data ? `${articles.length} articles · retrieved ${dateTime(data.sources[0]?.fetched_at)}` : 'Loading…'}
            right={articles.length > 0 && system?.providers.gemini && (
              <SentimentButton loading={sent.loading} done={articles.slice(0, 30).every((a) => sent.results[a.id])} onClick={() => sent.run(articles)} />
            )}
          />
          {sent.error && <div className="px-4 pb-2"><ErrorState compact error={sent.error} /></div>}
          {loading && !data ? <div className="space-y-3 px-4 pb-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
            : error ? <ErrorState error={error} onRetry={reload} />
            : !articles.length ? <EmptyState icon={<Newspaper size={18} />} title="No articles found">Try another category or company.</EmptyState>
            : <ul className="border-t border-line">{articles.map((a) => <NewsItem key={a.id} a={a} s={sent.results[a.id]} />)}</ul>}
          {data?.warnings.length ? <div className="border-t border-line px-4 py-2 text-[11px] text-warn">Some sources failed: {data.warnings.join(' · ')}</div> : null}
          {data?.sources.some((s) => s.stale) && <div className="border-t border-line px-4 py-2 text-[11px] text-warn">Some headlines are from the last successful retrieval because a news provider is unavailable.</div>}
        </Card>

        <div className="space-y-4">
          <SentimentSummary articles={articles} results={sent.results} />
          <Card className="p-4 text-xs leading-relaxed text-muted">
            <div className="mb-2 flex items-center gap-1.5 text-[13px] font-semibold text-ink"><Info size={14} /> Reading the news responsibly</div>
            <ul className="list-disc space-y-1.5 pl-4">
              <li><strong className="text-ink-2">Publication time ≠ market time.</strong> An article’s timestamp is when it was published, not when a price was recorded.</li>
              <li>Positive news does not guarantee a price rise — expectations are often already priced in.</li>
              <li>Sentiment labels come from AI reading only the headline and short summary.</li>
              <li>NewsAPI’s free Developer plan delays articles by 24 hours; Finnhub headlines may be more recent.</li>
              <li>Stock Sage shows headlines and summaries only. Click through to read the full article from its publisher.</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
