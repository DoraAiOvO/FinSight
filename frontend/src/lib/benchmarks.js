import { dataValue, fmtNum, fmtPct } from './api.js'

const PERCENT_METRICS = new Set([
  'revenue_growth',
  'profit_margin',
  'operating_margin',
  'free_cash_flow_margin',
  'dividend_yield',
])

export const BENCHMARK_SCOPES = ['industry', 'sector', 'peers', 'historical']

export function formatBenchmarkValue(metricKey, point, locale = 'en-US') {
  if (PERCENT_METRICS.has(metricKey)) return fmtPct(point, locale)
  if (metricKey === 'debt_to_equity') {
    const value = dataValue(point)
    return value == null ? '—' : `${Number(value).toLocaleString(locale, { maximumFractionDigits: 0 })}%`
  }
  return fmtNum(point, locale)
}

export function referenceFor(metric, scope) {
  return metric.references?.find((reference) => reference.scope === scope) || null
}

export function fillTemplate(template, params = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (match, name) => (
    params[name] == null ? match : String(params[name])
  ))
}
