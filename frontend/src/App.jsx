import { useState } from 'react'
import SearchBar from './components/SearchBar.jsx'
import StockOverview from './components/StockOverview.jsx'
import PriceChart from './components/PriceChart.jsx'
import AnalysisPanel from './components/AnalysisPanel.jsx'
import NewsFeed from './components/NewsFeed.jsx'
import CompareTable from './components/CompareTable.jsx'
import { api } from './lib/api.js'

export default function App() {
  const [mode, setMode] = useState('analyze') // 'analyze' | 'compare'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null) // { overview, history, analysis, news }
  const [compare, setCompare] = useState(null)

  async function analyze(ticker) {
    setLoading(true)
    setError(null)
    setCompare(null)
    try {
      const overview = await api.overview(ticker)
      const [history, analysis, news] = await Promise.allSettled([
        api.history(ticker),
        api.analysis(ticker),
        api.news(ticker),
      ])
      setData({
        overview,
        history: history.status === 'fulfilled' ? history.value : null,
        analysis: analysis.status === 'fulfilled' ? analysis.value : null,
        news: news.status === 'fulfilled' ? news.value : null,
      })
    } catch (e) {
      setError(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  async function runCompare(tickers) {
    setLoading(true)
    setError(null)
    setData(null)
    try {
      setCompare(await api.compare(tickers))
    } catch (e) {
      setError(e.message)
      setCompare(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="shell">
      <header className="header">
        <div className="brand">
          <span className="brand-mark">◆</span> FinSight
        </div>
        <p className="tagline">See beyond the numbers — we explain, you decide.</p>
      </header>

      <SearchBar
        mode={mode}
        onModeChange={setMode}
        onAnalyze={analyze}
        onCompare={runCompare}
        loading={loading}
      />

      {error && <div className="error-box">⚠ {error}</div>}
      {loading && <div className="loading">Crunching the numbers…</div>}

      {!loading && data && (
        <main className="results">
          <StockOverview overview={data.overview} />
          {data.history && <PriceChart history={data.history} />}
          <div className="two-col">
            {data.analysis && <AnalysisPanel analysis={data.analysis} />}
            {data.news && <NewsFeed news={data.news} />}
          </div>
        </main>
      )}

      {!loading && compare && <CompareTable data={compare} />}

      {!loading && !data && !compare && !error && (
        <div className="empty">
          <p>Search a ticker (e.g. <b>AAPL</b>) to see fundamentals, news themes, and an
          evidence-backed view of risks and opportunities — or switch to Compare to put
          up to five companies side by side.</p>
        </div>
      )}

      <footer className="footer">
        FinSight explains evidence; it does not give investment advice.
      </footer>
    </div>
  )
}
