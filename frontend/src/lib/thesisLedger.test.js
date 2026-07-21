import test from 'node:test'
import assert from 'node:assert/strict'

import {
  assumptionReady,
  assumptionStatusKey,
  buildAssumptionPayload,
  conditionSummary,
  ledgerEvidence,
  replaceAssumption,
} from './thesisLedger.js'


test('metric and event conditions clear mutually exclusive fields', () => {
  const metric = buildAssumptionPayload({
    description: ' Revenue growth stays high ',
    condition_type: 'metric',
    metric_key: ' revenue_growth ',
    operator: '>=',
    target_value: ' 20% ',
    event_condition: 'old event',
    current_status: 'monitoring',
    supporting_evidence: [],
    contradicting_evidence: [],
  })
  assert.equal(metric.metric_key, 'revenue_growth')
  assert.equal(metric.target_value, '20%')
  assert.equal(metric.event_condition, null)
  assert.equal(conditionSummary(metric), 'revenue_growth >= 20%')

  const event = buildAssumptionPayload({
    ...metric,
    condition_type: 'event',
    event_condition: ' No lower-priced competitor launches ',
  })
  assert.equal(event.metric_key, null)
  assert.equal(event.operator, null)
  assert.equal(event.target_value, null)
  assert.equal(event.event_condition, 'No lower-priced competitor launches')
  assert.equal(assumptionReady(event), true)
})


test('ledgerEvidence records source metadata without inventing a claim', () => {
  const now = new Date('2026-07-21T12:34:56Z')
  assert.deepEqual(ledgerEvidence({
    claim: ' Revenue grew 24%. ',
    source: ' Q2 earnings ',
    source_url: ' https://example.com/q2 ',
    confidence: '0.9',
  }, now), {
    claim: 'Revenue grew 24%.',
    source: 'Q2 earnings',
    source_url: 'https://example.com/q2',
    as_of_date: '2026-07-21',
    recorded_at: '2026-07-21T12:34:56.000Z',
    confidence: 0.9,
  })
})


test('assumption state helpers update only the selected thesis row', () => {
  const theses = [
    { id: 'one', assumptions: [{ id: 'a', current_status: 'monitoring' }] },
    { id: 'two', assumptions: [] },
  ]
  const result = replaceAssumption(
    theses,
    'one',
    { id: 'a', current_status: 'supported' },
  )
  assert.equal(result[0].assumptions[0].current_status, 'supported')
  assert.equal(result[1], theses[1])
  assert.equal(assumptionStatusKey('challenged'), 'assumptionChallenged')
})
