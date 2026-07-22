import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'
import { api } from '../lib/api.js'

const TICKER_PATTERN = /^[A-Z0-9][A-Z0-9.-]{0,9}$/
const SEARCH_DEBOUNCE_MS = 250
const MATCH_LABELS = {
  exact_ticker: 'matchExactTicker',
  exact_name: 'matchExactName',
  prefix: 'matchPrefix',
  partial_token: 'matchPartial',
  alias: 'matchAlias',
  localized_alias: 'matchLocalizedAlias',
  fuzzy: 'matchFuzzy',
}

function selectionLabel(company) {
  return `${company.company_name} · ${company.ticker}`
}

function directCompany(ticker) {
  return {
    ticker,
    company_name: ticker,
    exchange: '',
    sector: '',
    match_type: 'exact_ticker',
  }
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function HighlightedText({ text, query }) {
  const terms = query
    .trim()
    .split(/[\s,./_-]+/)
    .filter((term) => term.length > 1)
    .sort((left, right) => right.length - left.length)
  if (!text || terms.length === 0) return text

  const expression = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi')
  return text.split(expression).map((part, index) => (
    terms.some((term) => part.localeCompare(term, undefined, { sensitivity: 'accent' }) === 0)
      ? <mark key={`${part}-${index}`}>{part}</mark>
      : part
  ))
}

export default function SearchBar({ mode, onModeChange, onAnalyze, onCompare, loading }) {
  const { t } = useTranslation()
  const listboxId = useId()
  const inputRef = useRef(null)
  const requestSequence = useRef(0)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searchStatus, setSearchStatus] = useState('idle')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [validation, setValidation] = useState('')
  const [selectedCompany, setSelectedCompany] = useState(null)
  const [compareCompanies, setCompareCompanies] = useState([])

  useEffect(() => {
    setValidation('')
    setResults([])
    setSearchStatus('idle')
    setOpen(false)
    setActiveIndex(-1)
    setQuery(mode === 'analyze' && selectedCompany ? selectionLabel(selectedCompany) : '')
  }, [mode])

  useEffect(() => {
    const trimmed = query.trim()
    if (
      !trimmed
      || (mode === 'analyze' && selectedCompany && trimmed === selectionLabel(selectedCompany))
      || (mode === 'compare' && compareCompanies.length >= 5)
    ) {
      requestSequence.current += 1
      setResults([])
      setSearchStatus('idle')
      setOpen(false)
      setActiveIndex(-1)
      return undefined
    }

    const currentRequest = ++requestSequence.current
    const controller = new AbortController()
    setResults([])
    setSearchStatus('loading')
    setOpen(true)
    setActiveIndex(-1)

    const timeout = window.setTimeout(async () => {
      try {
        const matches = await api.searchCompanies(trimmed, 8, controller.signal)
        if (currentRequest !== requestSequence.current) return
        setResults(matches)
        setSearchStatus(matches.length > 0 ? 'success' : 'empty')
        setOpen(true)
      } catch (error) {
        if (error.name === 'AbortError' || currentRequest !== requestSequence.current) return
        setResults([])
        setSearchStatus('error')
        setOpen(true)
      }
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [query, mode, selectedCompany, compareCompanies.length])

  function clearSuggestions() {
    requestSequence.current += 1
    setResults([])
    setSearchStatus('idle')
    setOpen(false)
    setActiveIndex(-1)
  }

  function selectResult(company) {
    setValidation('')
    if (mode === 'compare') {
      if (compareCompanies.some((item) => item.ticker === company.ticker)) {
        setValidation(t('vDuplicate'))
        return
      }
      if (compareCompanies.length >= 5) {
        setValidation(t('vCompareFull'))
        return
      }
      setCompareCompanies((current) => [...current, company])
      setQuery('')
    } else {
      setSelectedCompany(company)
      setQuery(selectionLabel(company))
    }
    clearSuggestions()
    window.requestAnimationFrame(() => inputRef.current?.focus())
  }

  function addDirectTicker(ticker) {
    if (compareCompanies.some((company) => company.ticker === ticker)) {
      setValidation(t('vDuplicate'))
      return false
    }
    if (compareCompanies.length >= 5) {
      setValidation(t('vCompareFull'))
      return false
    }
    setCompareCompanies((current) => [...current, directCompany(ticker)])
    setQuery('')
    setValidation('')
    clearSuggestions()
    return true
  }

  function removeCompany(ticker) {
    setCompareCompanies((current) => current.filter((company) => company.ticker !== ticker))
    setValidation('')
    window.requestAnimationFrame(() => inputRef.current?.focus())
  }

  function directTickerFrom(raw) {
    const ticker = raw.toUpperCase()
    if (!TICKER_PATTERN.test(ticker)) return null
    const exactSearchMatch = results.some((result) => (
      result.match_type === 'exact_ticker' && result.ticker.toUpperCase() === ticker
    ))
    return raw === ticker || exactSearchMatch ? ticker : null
  }

  function submit(event) {
    event.preventDefault()
    const raw = query.trim()
    const directTicker = directTickerFrom(raw)

    if (mode === 'analyze') {
      if (selectedCompany) {
        setValidation('')
        onAnalyze(selectedCompany.ticker)
        return
      }
      if (directTicker) {
        setValidation('')
        onAnalyze(directTicker)
        return
      }
      setValidation(raw ? t('vSelectCompany') : t('vEnterCompany'))
      return
    }

    let companies = compareCompanies
    if (raw) {
      if (!directTicker) {
        setValidation(t('vSelectCompany'))
        return
      }
      if (companies.some((company) => company.ticker === directTicker)) {
        setValidation(t('vDuplicate'))
        return
      }
      if (companies.length >= 5) {
        setValidation(t('vCompareFull'))
        return
      }
      companies = [...companies, directCompany(directTicker)]
      setCompareCompanies(companies)
      setQuery('')
    }
    if (companies.length < 2 || companies.length > 5) {
      setValidation(t('vCompareCount'))
      return
    }

    setValidation('')
    onCompare(companies.map((company) => company.ticker))
  }

  function onInputChange(event) {
    if (mode === 'analyze') setSelectedCompany(null)
    setQuery(event.target.value)
    setValidation('')
  }

  function onInputKeyDown(event) {
    if (event.key === 'ArrowDown') {
      if (results.length === 0) return
      event.preventDefault()
      setOpen(true)
      setActiveIndex((current) => (current + 1) % results.length)
      return
    }
    if (event.key === 'ArrowUp') {
      if (results.length === 0) return
      event.preventDefault()
      setOpen(true)
      setActiveIndex((current) => (current <= 0 ? results.length - 1 : current - 1))
      return
    }
    if (event.key === 'Home' && open && results.length > 0) {
      event.preventDefault()
      setActiveIndex(0)
      return
    }
    if (event.key === 'End' && open && results.length > 0) {
      event.preventDefault()
      setActiveIndex(results.length - 1)
      return
    }
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
      setActiveIndex(-1)
      return
    }
    if (event.key === 'Enter' && open && activeIndex >= 0 && results[activeIndex]) {
      event.preventDefault()
      selectResult(results[activeIndex])
      return
    }
    if (event.key === 'Enter' && mode === 'compare') {
      const ticker = directTickerFrom(query.trim())
      if (ticker) {
        event.preventDefault()
        addDirectTicker(ticker)
      }
    }
  }

  const showPopup = open && searchStatus !== 'idle'
  const topResult = results[0]
  const activeOptionId = open && activeIndex >= 0
    ? `${listboxId}-option-${activeIndex}`
    : undefined
  const statusText = searchStatus === 'loading'
    ? t('searchLoading')
    : searchStatus === 'empty'
      ? t('searchEmpty')
      : searchStatus === 'error'
        ? t('searchError')
        : searchStatus === 'success'
          ? t('searchResultCount').replace('{count}', String(results.length))
          : ''

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
        <label htmlFor="company-search">
          {mode === 'compare' ? t('labelCompare') : t('labelAnalyze')}
        </label>
        {mode === 'compare' && compareCompanies.length > 0 && (
          <div className="company-chips" aria-label={t('selectedCompanies')}>
            {compareCompanies.map((company) => (
              <span className="company-chip" key={company.ticker}>
                <strong>{company.ticker}</strong>
                {company.company_name !== company.ticker && <span>{company.company_name}</span>}
                <button
                  type="button"
                  onClick={() => removeCompany(company.ticker)}
                  aria-label={t('removeCompany').replace('{company}', company.company_name)}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="combobox-shell">
          <div className="search-control">
            <span className="search-icon" aria-hidden="true" />
            <input
              ref={inputRef}
              id="company-search"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={showPopup}
              aria-controls={showPopup ? listboxId : undefined}
              aria-activedescendant={activeOptionId}
              aria-describedby={validation ? 'company-search-error' : 'company-search-status'}
              value={query}
              onChange={onInputChange}
              onKeyDown={onInputKeyDown}
              onFocus={() => searchStatus !== 'idle' && setOpen(true)}
              onBlur={() => setOpen(false)}
              placeholder={mode === 'compare' ? t('placeholderCompare') : t('placeholderAnalyze')}
              autoCapitalize="none"
              autoComplete="off"
              spellCheck="false"
              disabled={mode === 'compare' && compareCompanies.length >= 5}
            />
            <button type="submit" className="go" disabled={loading}>
              {loading ? t('working') : mode === 'compare' ? t('compareCta') : t('analyzeCta')}
              {!loading && <span aria-hidden="true">→</span>}
            </button>
          </div>

          {showPopup && (
            <div className="search-suggestions">
              <p className="search-status" aria-hidden="true">{statusText}</p>
              {searchStatus === 'success' && topResult?.match_type === 'fuzzy' && (
                <p className="did-you-mean">
                  {t('didYouMean')} <strong>{topResult.company_name} ({topResult.ticker})</strong>?
                </p>
              )}
              <ul id={listboxId} role="listbox" aria-label={t('searchResultsLabel')}>
                {results.map((result, index) => (
                  <li
                    id={`${listboxId}-option-${index}`}
                    key={`${result.ticker}-${result.exchange}`}
                    role="option"
                    aria-selected={activeIndex === index}
                    className={activeIndex === index ? 'active' : ''}
                    onMouseDown={(event) => {
                      event.preventDefault()
                      selectResult(result)
                    }}
                    onMouseMove={() => setActiveIndex(index)}
                  >
                    <div className="suggestion-primary">
                      <strong><HighlightedText text={result.company_name} query={query} /></strong>
                      <span><HighlightedText text={result.ticker} query={query} /></span>
                    </div>
                    <div className="suggestion-meta">
                      <span>{result.exchange}</span>
                      <span>{result.sector || t('unknownSector')}</span>
                      <span className={`match-reason match-${result.match_type}`}>
                        {t(MATCH_LABELS[result.match_type] || 'matchPartial')}
                        {result.matched_text && (
                          <> · <mark>{result.matched_text}</mark></>
                        )}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <span id="company-search-status" className="sr-only" aria-live="polite">
          {statusText}
        </span>
        {validation && <p id="company-search-error" className="field-error" role="alert">{validation}</p>}
      </form>
    </section>
  )
}
