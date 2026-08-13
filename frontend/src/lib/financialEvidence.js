const AI_SAFE_STATUSES = new Set([
  'OFFICIAL',
  'CROSS_VERIFIED',
  'SINGLE_SOURCE',
  'CALCULATED',
  'STALE',
])

const REPORTED_KEYS = new Set([
  'total_revenue',
  'free_cash_flow',
  'profit_margin',
  'operating_margin',
  'debt_to_equity',
])

export function selectedFinancialMetrics(evidence) {
  const metricMap = new Map((evidence?.metrics || []).map((metric) => [metric.metric_id, metric]))
  const latest = new Map()
  ;(evidence?.verification_results || []).forEach((result) => {
    if (!AI_SAFE_STATUSES.has(result.verification_status)) return
    const metric = metricMap.get(result.selected_metric_id)
    if (!metric) return
    const current = latest.get(metric.metric_key)
    if (!current || metric.period_end > current.period_end) latest.set(metric.metric_key, metric)
  })
  return latest
}

export function applyFinancialEvidence(overview, evidence) {
  const normalized = { ...overview }
  const selected = selectedFinancialMetrics(evidence)
  REPORTED_KEYS.forEach((key) => {
    if (!selected.has(key)) normalized[key] = null
  })
  selected.forEach((metric, key) => {
    if (!Object.hasOwn(normalized, key)) return
    const debtRatio = key === 'debt_to_equity' && metric.unit === 'ratio'
    normalized[key] = {
      value: debtRatio ? metric.value * 100 : metric.value,
      unit: debtRatio ? 'percent' : (metric.currency || metric.unit),
      display_value: null,
      provider: metric.provider,
      source: metric.source_concept,
      as_of_date: metric.period_end,
      fetched_at: metric.fetched_at,
      freshness_status: metric.verification_status === 'STALE' ? 'stale' : 'historical',
      verification_status: metric.verification_status,
      source_url: metric.source_document,
    }
  })
  return normalized
}
