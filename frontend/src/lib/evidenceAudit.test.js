import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyAuditResult,
  auditCheckedText,
  auditCheckRows,
  auditStatusKey,
  buildAuditDraft,
  buildComparisonAuditDraft,
} from './evidenceAudit.js'


test('buildAuditDraft includes every visible report section', () => {
  const generatedAt = new Date('2026-07-21T12:00:00Z')
  const draft = buildAuditDraft({
    generatedAt,
    overview: { ticker: 'TEST' },
    history: { points: [] },
    analysis: { insights: [] },
    news: null,
    filings: { filings: [] },
    valuation: { ticker: 'TEST' },
  })

  assert.equal(draft.captured_at, generatedAt.toISOString())
  assert.equal(draft.overview.ticker, 'TEST')
  assert.deepEqual(draft.history.points, [])
  assert.equal(draft.news, null)
})


test('applyAuditResult replaces the draft with sanitized sections', () => {
  const current = { overview: { ticker: 'TEST' }, news: { ai_summary: 'unsafe' } }
  const audit = { status: 'blocked', issue_counts: { unsupported_claim: 1 } }
  const result = applyAuditResult(current, {
    report: {
      captured_at: '2026-07-21T12:00:00Z',
      overview: current.overview,
      news: { ai_summary: null },
    },
    audit,
  })

  assert.equal(result.news.ai_summary, null)
  assert.equal(result.audit, audit)
  assert.equal(result.generatedAt.toISOString(), '2026-07-21T12:00:00.000Z')
})


test('buildComparisonAuditDraft wraps peer reports for the same audit gate', () => {
  const comparison = { tickers: ['AAA', 'BBB'], rows: [] }
  const draft = buildComparisonAuditDraft(comparison, '2026-07-21T12:00:00Z')

  assert.equal(draft.captured_at, '2026-07-21T12:00:00Z')
  assert.equal(draft.comparison, comparison)
})


test('audit helpers expose all six checks in a stable order', () => {
  const rows = auditCheckRows({ issue_counts: { stale_evidence: 2 } })
  assert.equal(rows.length, 6)
  assert.deepEqual(rows.find((row) => row.code === 'stale_evidence'), {
    code: 'stale_evidence',
    count: 2,
  })
  assert.equal(auditStatusKey('passed'), 'auditStatusPassed')
  assert.equal(auditStatusKey('blocked'), 'auditStatusBlocked')
})


test('audit checked copy interpolates evidence and data point totals', () => {
  assert.equal(
    auditCheckedText(
      'Checked {evidence} evidence items and {points} data points',
      { evidence_checked: 7, data_points_checked: 23 },
    ),
    'Checked 7 evidence items and 23 data points',
  )
})
