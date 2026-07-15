import { useEffect, useState } from 'react'

const TICKER_PATTERN = /^[A-Z0-9][A-Z0-9.-]{0,9}$/

export default function SearchBar({ mode, onModeChange, onAnalyze, onCompare, loading }) {
  const [query, setQuery] = useState('')
  const [validation, setValidation] = useState('')

  useEffect(() => setValidation(''), [mode])

  function submit(event) {
    event.preventDefault()
    const raw = query.trim().toUpperCase()
    const tickers = raw.split(/[,\s]+/).filter(Boolean)

    if (!raw) {
      setValidation('Enter a ticker to begin.')
      return
    }
    if (tickers.some((ticker) => !TICKER_PATTERN.test(ticker))) {
      setValidation('Use ticker symbols only, such as BRK-B or RDS.A.')
      return
    }
    if (mode === 'compare' && (tickers.length < 2 || tickers.length > 5)) {
      setValidation('Enter between two and five tickers to compare.')
      return
    }
    if (mode === 'analyze' && tickers.length > 1) {
      setValidation('Enter one ticker, or switch to Compare for multiple companies.')
      return
    }
    if (new Set(tickers).size !== tickers.length) {
      setValidation('Use each ticker only once.')
      return
    }

    setValidation('')
    if (mode === 'compare') onCompare(tickers)
    else onAnalyze(tickers[0])
  }

  return (
    <section className="search-panel" aria-label="Stock research search">
      <div className="mode-toggle" aria-label="Research mode">
        <button
          type="button"
          className={mode === 'analyze' ? 'active' : ''}
          aria-pressed={mode === 'analyze'}
          onClick={() => onModeChange('analyze')}
        >
          Company
        </button>
        <button
          type="button"
          className={mode === 'compare' ? 'active' : ''}
          aria-pressed={mode === 'compare'}
          onClick={() => onModeChange('compare')}
        >
          Compare
        </button>
      </div>
      <form className="search-form" onSubmit={submit}>
        <label htmlFor="ticker-search">
          {mode === 'compare' ? 'Compare 2–5 companies' : 'Research a public company'}
        </label>
        <div className="search-control">
          <span className="search-icon" aria-hidden="true" />
          <input
            id="ticker-search"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setValidation('') }}
            placeholder={mode === 'compare' ? 'AAPL, MSFT, GOOGL' : 'Enter a ticker, e.g. AAPL'}
            autoCapitalize="characters"
            autoComplete="off"
            spellCheck="false"
          />
          <button type="submit" className="go" disabled={loading}>
            {loading ? 'Working…' : mode === 'compare' ? 'Compare companies' : 'Build research brief'}
            {!loading && <span aria-hidden="true">→</span>}
          </button>
        </div>
        {validation && <p className="field-error" role="alert">{validation}</p>}
      </form>
    </section>
  )
}
