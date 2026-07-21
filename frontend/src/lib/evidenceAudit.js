export const AUDIT_CHECKS = [
  'unsupported_claim',
  'stale_evidence',
  'missing_citation',
  'conflicting_sources',
  'incorrect_unit',
  'inconsistent_number',
]

export function buildAuditDraft(data) {
  if (!data?.overview) throw new Error('A report overview is required for auditing')
  const capturedAt = data.generatedAt instanceof Date
    ? data.generatedAt.toISOString()
    : data.generatedAt || new Date().toISOString()
  return {
    captured_at: capturedAt,
    overview: data.overview,
    history: data.history || null,
    analysis: data.analysis || null,
    news: data.news || null,
    filings: data.filings || null,
    valuation: data.valuation || null,
  }
}

export function buildComparisonAuditDraft(comparison, capturedAt = new Date()) {
  if (!comparison?.tickers || !comparison?.rows) {
    throw new Error('A completed comparison is required for auditing')
  }
  return {
    captured_at: capturedAt instanceof Date ? capturedAt.toISOString() : capturedAt,
    comparison,
  }
}

export function applyAuditResult(current, result) {
  if (!result?.report || !result?.audit) throw new Error('Evidence audit response is incomplete')
  return {
    ...current,
    ...result.report,
    generatedAt: new Date(result.report.captured_at),
    audit: result.audit,
  }
}

export function auditCheckRows(audit) {
  const counts = audit?.issue_counts || {}
  return AUDIT_CHECKS.map((code) => ({ code, count: counts[code] || 0 }))
}

export function auditStatusKey(status) {
  return {
    passed: 'auditStatusPassed',
    warning: 'auditStatusWarning',
    blocked: 'auditStatusBlocked',
  }[status] || 'auditStatusWarning'
}
