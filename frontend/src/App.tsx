import { lazy } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AppProvider } from './lib/AppContext'
import { Layout } from './components/layout/Layout'
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Explore = lazy(() => import('./pages/Explore'))
const StockDetail = lazy(() => import('./pages/StockDetail'))
const AIAnalyst = lazy(() => import('./pages/AIAnalyst'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const PaperTrading = lazy(() => import('./pages/PaperTrading'))
const News = lazy(() => import('./pages/News'))
const Learn = lazy(() => import('./pages/Learn'))
const Settings = lazy(() => import('./pages/Settings'))
import { EmptyState } from './components/ui/states'
import { Button } from './components/ui/primitives'

function NotFound() {
  return (
    <EmptyState title="Page not found" action={<Link to="/"><Button variant="primary">Back to dashboard</Button></Link>}>
      The page you’re looking for doesn’t exist.
    </EmptyState>
  )
}

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="explore" element={<Explore />} />
            <Route path="stocks/:symbol" element={<StockDetail />} />
            <Route path="analyst" element={<AIAnalyst />} />
            <Route path="watchlist" element={<Watchlist />} />
            <Route path="portfolio" element={<Portfolio />} />
            <Route path="trade" element={<PaperTrading />} />
            <Route path="news" element={<News />} />
            <Route path="learn" element={<Learn />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  )
}
