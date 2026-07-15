import { useState } from 'react'

export default function SearchBar({ mode, onModeChange, onAnalyze, onCompare, loading }) {
  const [query, setQuery] = useState('')

  function submit(e) {
    e.preventDefault()
    const raw = query.trim().toUpperCase()
    if (!raw) return
    if (mode === 'compare') {
      const tickers = raw.split(/[,\s]+/).filter(Boolean)
      if (tickers.length >= 2) onCompare(tickers)
    } else {
      onAnalyze(raw.split(/[,\s]+/)[0])
    }
  }

  return (
    <form className="search" onSubmit={submit}>
      <div className="mode-toggle" role="tablist">
        <button
          type="button"
          className={mode === 'analyze' ? 'active' : ''}
          onClick={() => onModeChange('analyze')}
        >
          Analyze
        </button>
        <button
          type="button"
          className={mode === 'compare' ? 'active' : ''}
          onClick={() => onModeChange('compare')}
        >
          Compare
        </button>
      </div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={mode === 'compare' ? 'AAPL, MSFT, GOOGL (2–5 tickers)' : 'Ticker, e.g. AAPL'}
        aria-label="Ticker search"
      />
      <button type="submit" className="go" disabled={loading}>
        {mode === 'compare' ? 'Compare' : 'Analyze'}
      </button>
    </form>
  )
}
