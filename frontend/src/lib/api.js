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
