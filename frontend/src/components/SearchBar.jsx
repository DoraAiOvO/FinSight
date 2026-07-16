import { useEffect, useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'

const TICKER_PATTERN = /^[A-Z0-9][A-Z0-9.-]{0,9}$/

export default function SearchBar({ mode, onModeChange, onAnalyze, onCompare, loading }) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [validation, setValidation] = useState('')

  useEffect(() => setValidation(''), [mode])

  function submit(event) {
    event.preventDefault()
    const raw = query.trim().toUpperCase()
    const tickers = raw.split(/[,\s]+/).filter(Boolean)

    if (!raw) {
      setValidation(t('vEnterTicker'))
      return
    }
    if (tickers.some((ticker) => !TICKER_PATTERN.test(ticker))) {
      setValidation(t('vTickerFormat'))
      return
    }
    if (mode === 'compare' && (tickers.length < 2 || tickers.length > 5)) {
      setValidation(t('vCompareCount'))
      return
    }
    if (mode === 'analyze' && tickers.length > 1) {
      setValidation(t('vOneTicker'))
      return
    }
    if (new Set(tickers).size !== tickers.length) {
      setValidation(t('vDuplicate'))
      return
    }

    setValidation('')
    if (mode === 'compare') onCompare(tickers)
    else onAnalyze(tickers[0])
  }

  return (
    <section className="search-panel" aria-label={t('searchAriaLabel')}>
      <div className="mode-toggle" aria-label={t('modeAriaLabel')}>
        <button
          type="button"
          className={mode === 'analyze' ? 'active' : ''}
          aria-pressed={mode === 'analyze'}
          onClick={() => onModeChange('analyze')}
        >
          {t('modeCompany')}
        </button>
        <button
          type="button"
          className={mode === 'compare' ? 'active' : ''}
          aria-pressed={mode === 'compare'}
          onClick={() => onModeChange('compare')}
        >
          {t('modeCompare')}
        </button>
      </div>
      <form className="search-form" onSubmit={submit}>
        <label htmlFor="ticker-search">
          {mode === 'compare' ? t('labelCompare') : t('labelAnalyze')}
        </label>
        <div className="search-control">
          <span className="search-icon" aria-hidden="true" />
          <input
            id="ticker-search"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setValidation('') }}
            placeholder={mode === 'compare' ? t('placeholderCompare') : t('placeholderAnalyze')}
            autoCapitalize="characters"
            autoComplete="off"
            spellCheck="false"
          />
          <button type="submit" className="go" disabled={loading}>
            {loading ? t('working') : mode === 'compare' ? t('compareCta') : t('analyzeCta')}
            {!loading && <span aria-hidden="true">→</span>}
          </button>
        </div>
        {validation && <p className="field-error" role="alert">{validation}</p>}
      </form>
    </section>
  )
}
