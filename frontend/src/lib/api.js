async function get(path) {
  const res = await fetch(path)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export const api = {
  overview: (ticker) => get(`/api/stocks/${encodeURIComponent(ticker)}`),
  history: (ticker, period = '6mo') =>
    get(`/api/stocks/${encodeURIComponent(ticker)}/history?period=${period}`),
  news: (ticker, lang = 'en') =>
    get(`/api/news/${encodeURIComponent(ticker)}?lang=${encodeURIComponent(lang)}`),
  analysis: (ticker, lang = 'en') =>
    get(`/api/analysis/${encodeURIComponent(ticker)}?lang=${encodeURIComponent(lang)}`),
  compare: (tickers) => get(`/api/compare?tickers=${encodeURIComponent(tickers.join(','))}`),
}

export function fmtBig(v) {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + 'T'
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + 'B'
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + 'M'
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

export function fmtPct(v) {
  return v == null ? '—' : (v * 100).toFixed(1) + '%'
}

export function fmtNum(v) {
  return v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
}
