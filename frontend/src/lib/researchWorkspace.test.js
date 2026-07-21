import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildResearchSnapshot,
  changeDirectionKey,
  changeItemTitle,
  metricDisplay,
  visibleChanges,
} from './researchWorkspace.js'


test('buildResearchSnapshot keeps the six change-report evidence inputs', () => {
  const generatedAt = new Date('2026-07-20T12:00:00Z')
  const data = {
    generatedAt,
    overview: { ticker: 'AAPL' },
    analysis: { ticker: 'AAPL', insights: [] },
    news: { ticker: 'AAPL', items: [] },
    filings: { ticker: 'AAPL', filings: [] },
    thesisAssumptions: [{ description: 'Growth remains positive' }],
  }

  assert.deepEqual(buildResearchSnapshot(data), {
    captured_at: generatedAt.toISOString(),
    overview: data.overview,
    analysis: data.analysis,
    news: data.news,
    filings: data.filings,
    thesis_assumptions: data.thesisAssumptions,
  })
})


test('visibleChanges removes unchanged rows from noisy deterministic categories', () => {
  const items = [
    { direction: 'unchanged', label: 'Price' },
    { direction: 'improved', label: 'Revenue growth' },
  ]
  assert.deepEqual(visibleChanges('financial_metrics', items), [items[1]])
  assert.deepEqual(visibleChanges('news', items), items)
})


test('workspace display helpers preserve evidence labels and direction keys', () => {
  assert.equal(changeDirectionKey('worsened'), 'changeWorsened')
  assert.equal(metricDisplay({ display_value: '$101.50', value: 101.5 }, 'en-US'), '$101.50')
  assert.equal(changeItemTitle('news', {
    item: { title: { claim: 'Quarterly results released' } },
  }), 'Quarterly results released')
})
