import { displayDataPoint } from './api.js'

export const CHANGE_SECTIONS = [
  { key: 'financial_metrics', titleKey: 'changedMetrics' },
  { key: 'news', titleKey: 'changedNews' },
  { key: 'filings', titleKey: 'changedFilings' },
  { key: 'risk_signals', titleKey: 'changedRisks' },
  { key: 'opportunity_signals', titleKey: 'changedOpportunities' },
  { key: 'thesis_assumptions', titleKey: 'changedAssumptions' },
]

export function buildResearchSnapshot(data) {
  if (!data?.overview) throw new Error('A completed research report is required')
  const capturedAt = data.generatedAt instanceof Date
    ? data.generatedAt.toISOString()
    : data.generatedAt || new Date().toISOString()
  return {
    captured_at: capturedAt,
    overview: data.overview,
    analysis: data.analysis || null,
    news: data.news || null,
    filings: data.filings || null,
    thesis_assumptions: data.thesisAssumptions || [],
  }
}

export function visibleChanges(sectionKey, items = []) {
  if (sectionKey === 'financial_metrics'
      || sectionKey === 'risk_signals'
      || sectionKey === 'opportunity_signals'
      || sectionKey === 'thesis_assumptions') {
    return items.filter((item) => item.direction !== 'unchanged')
  }
  return items
}

export function changeDirectionKey(direction) {
  return {
    new: 'changeNew',
    removed: 'changeRemoved',
    improved: 'changeImproved',
    worsened: 'changeWorsened',
    changed: 'changeChanged',
    resolved: 'changeResolved',
    unchanged: 'changeUnchanged',
  }[direction] || 'changeChanged'
}

export function metricDisplay(point, locale) {
  const value = displayDataPoint(point)
  if (value == null) return '—'
  if (typeof value === 'number') {
    return value.toLocaleString(locale, { maximumFractionDigits: 3 })
  }
  return String(value)
}

export function changeItemTitle(sectionKey, item) {
  if (sectionKey === 'financial_metrics') return item.label
  if (sectionKey === 'news') return item.item?.title?.claim || ''
  if (sectionKey === 'filings') {
    const filing = item.filing
    return filing ? `${filing.filing_type} · ${filing.filing_date}` : ''
  }
  if (sectionKey === 'thesis_assumptions') return item.description
  return item.title?.claim || item.code || ''
}
