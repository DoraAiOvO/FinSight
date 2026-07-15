import { useRef, useState } from 'react'
import SearchBar from './components/SearchBar.jsx'
import StockOverview from './components/StockOverview.jsx'
import PriceChart from './components/PriceChart.jsx'
import AnalysisPanel from './components/AnalysisPanel.jsx'
import NewsFeed from './components/NewsFeed.jsx'
import CompareTable from './components/CompareTable.jsx'
import { api } from './lib/api.js'

const STARTER_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'COST']

function LoadingReport({ mode }) {
  return (
    <main className="results loading-report" aria-live="polite" aria-busy="true">
      <div className="loading-copy">
        <span className="loading-pulse" />
        {mode === 'compare' ? 'Building a consistent comparison…' : 'Gathering the evidence…'}
      </div>
      <div className="skeleton skeleton-hero" />
      <div className="skeleton-grid">
        <div className="skeleton" />
        <div className="skeleton" />
      </div>
    </main>
  )
}

function EmptyState({ onAnalyze }) {
  return (
    <main className="landing">
      <section className="hero-copy">
        <p className="eyebrow">Evidence-first equity research</p>
        <h1>See the business <em>behind the ticker.</em></h1>
        <p className="hero-lede">
          Turn fundamentals, price movement, recent news, and risk signals into one
          balanced research brief you can actually follow.
        </p>
        <div className="starter-row" aria-label="Try a popular ticker">
          <span>Start with</span>
          {STARTER_TICKERS.map((ticker) => (
            <button key={ticker} type="button" onClick={() => onAnalyze(ticker)}>
              {ticker}
            </button>
          ))}
        </div>
      </section>

      <section className="method-card" aria-labelledby="method-title">
        <div className="method-topline">
          <span className="method-kicker">How FinSight works</span>
          <span className="method-badge">No black box</span>
        </div>
        <h2 id="method-title">A research trail, not a verdict.</h2>
        <ol className="method-list">
          <li>
            <span>01</span>
            <div><strong>Collect</strong><small>Fundamentals, pricing, and news</small></div>
          </li>
          <li>
            <span>02</span>
            <div><strong>Test</strong><small>Metrics against visible benchmarks</small></div>
          </li>
          <li>
            <span>03</span>
            <div><strong>Explain</strong><small>Risks and opportunities together</small></div>
          </li>
        </ol>
      </section>
    </main>
  )
}

export default function App() {
  const [mode, setMode] = useState('analyze')
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notices, setNotices] = useState([])
  const [data, setData] = useState(null)
  const [compare, setCompare] = useState(null)
  const requestId = useRef(0)

  function changeMode(nextMode) {
    setMode(nextMode)
    setError(null)
  }

  function resetHome() {
    requestId.current += 1
    setLoading(false)
    setHistoryLoading(false)
    setError(null)
    setNotices([])
    setData(null)
    setCompare(null)
  }

  async function analyze(ticker) {
    const currentRequest = ++requestId.current
    setMode('analyze')
    setLoading(true)
    setHistoryLoading(false)
    setError(null)
    setNotices([])
    setCompare(null)

    try {
      const overview = await api.overview(ticker)
      const sections = await Promise.allSettled([
        api.history(ticker, '6mo'),
        api.analysis(ticker),
        api.news(ticker),
      ])
      if (currentRequest !== requestId.current) return

      const sectionNames = ['Price history', 'Risk analysis', 'Recent news']
      const unavailable = sections.flatMap((result, index) =>
        result.status === 'rejected' ? [`${sectionNames[index]} is temporarily unavailable.`] : [],
      )
      setNotices(unavailable)
      setData({
        overview,
        history: sections[0].status === 'fulfilled' ? sections[0].value : null,
        analysis: sections[1].status === 'fulfilled' ? sections[1].value : null,
        news: sections[2].status === 'fulfilled' ? sections[2].value : null,
        generatedAt: new Date(),
      })
    } catch (requestError) {
      if (currentRequest !== requestId.current) return
      setError(requestError.message)
      setData(null)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }

  async function changePeriod(nextPeriod) {
    if (!data || nextPeriod === data.history?.period) return
    const parentRequest = requestId.current
    setHistoryLoading(true)
    try {
      const history = await api.history(data.overview.ticker, nextPeriod)
      if (parentRequest !== requestId.current) return
      setData((current) => current && { ...current, history })
      setNotices((current) => current.filter((notice) => !notice.startsWith('Price history')))
    } catch (requestError) {
      if (parentRequest !== requestId.current) return
      setNotices((current) => [
        ...current.filter((notice) => !notice.startsWith('Price history')),
        `Price history could not be updated: ${requestError.message}`,
      ])
    } finally {
      if (parentRequest === requestId.current) setHistoryLoading(false)
    }
  }

  async function runCompare(tickers) {
    const currentRequest = ++requestId.current
    setLoading(true)
    setHistoryLoading(false)
    setError(null)
    setNotices([])
    setData(null)
    try {
      const result = await api.compare(tickers)
      if (currentRequest === requestId.current) setCompare(result)
    } catch (requestError) {
      if (currentRequest !== requestId.current) return
      setError(requestError.message)
      setCompare(null)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <button className="brand" type="button" onClick={resetHome} aria-label="Go to FinSight home">
          <span className="brand-mark" aria-hidden="true"><i /></span>
          <span>FinSight</span>
        </button>
        <div className="header-note">
          <span className="status-dot" />
          Research assistant · Not investment advice
        </div>
      </header>

      <SearchBar
        mode={mode}
        onModeChange={changeMode}
        onAnalyze={analyze}
        onCompare={runCompare}
        loading={loading}
      />

      {error && (
        <div className="message error-box" role="alert">
          <strong>We couldn’t build that report.</strong>
          <span>{error}</span>
        </div>
      )}

      {notices.length > 0 && !loading && (
        <div className="message notice-box" role="status">
          <strong>Partial report</strong>
          <span>{notices.join(' ')}</span>
        </div>
      )}

      {loading && <LoadingReport mode={mode} />}

      {!loading && data && (
        <main className="results">
          <div className="report-heading">
            <div>
              <p className="eyebrow">Research brief · {data.overview.ticker}</p>
              <h1>A balanced view of <em>the evidence</em></h1>
            </div>
            <p className="report-time">
              Generated {data.generatedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
              <span>Yahoo Finance data may be delayed</span>
            </p>
          </div>
          <StockOverview overview={data.overview} />
          {data.history && (
            <PriceChart
              history={data.history}
              loading={historyLoading}
              onPeriodChange={changePeriod}
            />
          )}
          <div className="research-grid">
            {data.analysis && <AnalysisPanel analysis={data.analysis} />}
            {data.news && <NewsFeed news={data.news} />}
          </div>
        </main>
      )}

      {!loading && compare && (
        <main className="results">
          <div className="report-heading">
            <div>
              <p className="eyebrow">Peer research</p>
              <h1>Compare the evidence, <em>metric by metric.</em></h1>
            </div>
          </div>
          <CompareTable data={compare} />
        </main>
      )}

      {!loading && !data && !compare && !error && <EmptyState onAnalyze={analyze} />}

      <footer className="site-footer">
        <div><span className="brand-mini">FS</span> See beyond the numbers.</div>
        <p>Educational research only. Verify important information independently.</p>
      </footer>
    </div>
  )
}
