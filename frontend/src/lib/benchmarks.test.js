import test from 'node:test'
import assert from 'node:assert/strict'
import { fillTemplate, formatBenchmarkValue, referenceFor } from './benchmarks.js'

test('formats ratios, leverage, and multiples for benchmark tables', () => {
  assert.equal(formatBenchmarkValue('profit_margin', { value: 0.237 }, 'en-US'), '23.7%')
  assert.equal(formatBenchmarkValue('debt_to_equity', { value: 142.4 }, 'en-US'), '142%')
  assert.equal(formatBenchmarkValue('trailing_pe', { value: 28.456 }, 'en-US'), '28.46')
})

test('finds scope references and fills translated rationale templates', () => {
  const metric = { references: [{ scope: 'sector', sample_size: 5 }] }
  assert.equal(referenceFor(metric, 'sector').sample_size, 5)
  assert.equal(referenceFor(metric, 'industry'), null)
  assert.equal(
    fillTemplate('{sampleSize} companies in {name}', { sampleSize: 4, name: 'Software' }),
    '4 companies in Software',
  )
})
