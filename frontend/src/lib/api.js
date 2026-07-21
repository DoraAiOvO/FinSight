async function request(path, options) {
  const res = await fetch(path, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const error = new Error(body.detail || `Request failed (${res.status})`)
    error.status = res.status
    throw error
  }
  if (res.status === 204) return null
  return res.json()
}

const get = (path) => request(path)
const write = (path, method, body) => request(path, {
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  overview: (ticker) => get(`/api/stocks/${encodeURIComponent(ticker)}`),
  history: (ticker, period = '6mo') =>
    get(`/api/stocks/${encodeURIComponent(ticker)}/history?period=${period}`),
  news: (ticker, lang = 'en') =>
    get(`/api/news/${encodeURIComponent(ticker)}?lang=${encodeURIComponent(lang)}`),
  analysis: (ticker, lang = 'en', customerId = null) => {
    const params = new URLSearchParams({ lang })
    if (customerId) params.set('customer_id', customerId)
    return get(`/api/analysis/${encodeURIComponent(ticker)}?${params}`)
  },
  compare: (tickers) => get(`/api/compare?tickers=${encodeURIComponent(tickers.join(','))}`),
  filings: (ticker, limit = 12) => (
    get(`/api/filings/${encodeURIComponent(ticker)}?limit=${limit}`)
  ),
  filing: (ticker, accessionNumber) => (
    get(`/api/filings/${encodeURIComponent(ticker)}/${encodeURIComponent(accessionNumber)}`)
  ),
  askFiling: (ticker, accessionNumber, question, lang = 'en') => (
    write(
      `/api/filings/${encodeURIComponent(ticker)}/${encodeURIComponent(accessionNumber)}/questions`,
      'POST',
      { question, lang },
    )
  ),
  customerProfile: {
    create: (profile) => write('/api/customer-profiles', 'POST', profile),
    get: (customerId) => get(`/api/customer-profiles/${encodeURIComponent(customerId)}`),
    update: (customerId, profile) => (
      write(`/api/customer-profiles/${encodeURIComponent(customerId)}`, 'PUT', profile)
    ),
  },
  watchlists: {
    list: (customerId) => get(`/api/customers/${encodeURIComponent(customerId)}/watchlists`),
    create: (customerId, watchlist) => write(
      `/api/customers/${encodeURIComponent(customerId)}/watchlists`,
      'POST',
      watchlist,
    ),
    remove: (customerId, watchlistId) => request(
      `/api/customers/${encodeURIComponent(customerId)}/watchlists/${encodeURIComponent(watchlistId)}`,
      { method: 'DELETE' },
    ),
    addItem: (customerId, watchlistId, item) => write(
      `/api/customers/${encodeURIComponent(customerId)}/watchlists/${encodeURIComponent(watchlistId)}/items`,
      'POST',
      item,
    ),
    removeItem: (customerId, watchlistId, ticker) => request(
      `/api/customers/${encodeURIComponent(customerId)}/watchlists/${encodeURIComponent(watchlistId)}/items/${encodeURIComponent(ticker)}`,
      { method: 'DELETE' },
    ),
  },
  researchSessions: {
    list: (customerId, ticker = null, limit = 20) => {
      const params = new URLSearchParams({ limit: String(limit) })
      if (ticker) params.set('ticker', ticker)
      return get(`/api/customers/${encodeURIComponent(customerId)}/research-sessions?${params}`)
    },
    create: (customerId, research) => write(
      `/api/customers/${encodeURIComponent(customerId)}/research-sessions`,
      'POST',
      research,
    ),
    get: (customerId, researchSessionId) => get(
      `/api/customers/${encodeURIComponent(customerId)}/research-sessions/${encodeURIComponent(researchSessionId)}`,
    ),
    remove: (customerId, researchSessionId) => request(
      `/api/customers/${encodeURIComponent(customerId)}/research-sessions/${encodeURIComponent(researchSessionId)}`,
      { method: 'DELETE' },
    ),
    whatChanged: (customerId, ticker, snapshot, baselineSessionId = null) => write(
      `/api/customers/${encodeURIComponent(customerId)}/what-changed/${encodeURIComponent(ticker)}`,
      'POST',
      {
        snapshot,
        ...(baselineSessionId ? { baseline_session_id: baselineSessionId } : {}),
      },
    ),
  },
}

export function dataValue(point) {
  if (point == null) return null
  return typeof point === 'object' && Object.hasOwn(point, 'value') ? point.value : point
}

export function evidenceText(item) {
  if (item == null) return null
  return typeof item === 'object' && Object.hasOwn(item, 'claim') ? item.claim : item
}

export function displayDataPoint(point) {
  if (point == null) return null
  if (typeof point === 'object' && point.display_value != null) return point.display_value
  return dataValue(point)
}

export function fmtBig(v, locale) {
  v = dataValue(v)
  if (v == null) return '—'
  const abs = Math.abs(v)
  const scaled = (value, suffix) => value.toLocaleString(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) + suffix
  if (abs >= 1e12) return scaled(v / 1e12, 'T')
  if (abs >= 1e9) return scaled(v / 1e9, 'B')
  if (abs >= 1e6) return scaled(v / 1e6, 'M')
  return v.toLocaleString(locale, { maximumFractionDigits: 2 })
}

export function fmtPct(v, locale) {
  v = dataValue(v)
  return v == null ? '—' : (v * 100).toLocaleString(locale, { maximumFractionDigits: 1 }) + '%'
}

export function fmtNum(v, locale) {
  v = dataValue(v)
  return v == null ? '—' : Number(v).toLocaleString(locale, { maximumFractionDigits: 2 })
}
