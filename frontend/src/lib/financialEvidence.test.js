import assert from 'node:assert/strict'
import test from 'node:test'

import { applyFinancialEvidence, selectedFinancialMetrics } from './financialEvidence.js'

const official = {
  metric_id: 'sec-revenue',
  metric_key: 'total_revenue',
  value: 100,
  currency: 'USD',
  unit: 'currency',
  provider: 'SEC EDGAR',
  source_concept: 'us-gaap:Revenue',
  source_document: 'https://sec.example/filing',
  period_end: '2025-12-31',
  fetched_at: '2026-02-01T00:00:00Z',
  verification_status: 'CROSS_VERIFIED',
}

test('official selected evidence replaces a Yahoo reported overview value', () => {
  const evidence = {
    metrics: [official],
    verification_results: [{
      metric_key: 'total_revenue',
      selected_metric_id: official.metric_id,
      verification_status: 'CROSS_VERIFIED',
    }],
  }
  const overview = applyFinancialEvidence({ total_revenue: { value: 99 } }, evidence)
  assert.equal(overview.total_revenue.value, 100)
  assert.equal(overview.total_revenue.provider, 'SEC EDGAR')
})

test('conflicting evidence is not passed through the legacy overview', () => {
  const evidence = {
    metrics: [{ ...official, verification_status: 'CONFLICTING' }],
    verification_results: [{
      metric_key: 'total_revenue',
      selected_metric_id: official.metric_id,
      verification_status: 'CONFLICTING',
    }],
  }
  assert.equal(selectedFinancialMetrics(evidence).size, 0)
  assert.equal(applyFinancialEvidence({ total_revenue: { value: 99 } }, evidence).total_revenue, null)
})
