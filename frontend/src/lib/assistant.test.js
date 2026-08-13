import test from 'node:test'
import assert from 'node:assert/strict'
import { assistantUi, buildAssistantReportContext } from './assistant.js'
import { LANGUAGES } from './language.js'

test('additional assistant languages do not change website language options', () => {
  assert.deepEqual(LANGUAGES, ['en', 'es', 'fr', 'zh'])
})

test('Chinese assistant UI uses localized stock-symbol terminology', () => {
  const copy = assistantUi('zh')
  const allText = JSON.stringify(copy).toLowerCase()

  assert.match(allText, /股票代码/)
  assert.doesNotMatch(allText, /ticker/)
})

test('assistant report evidence labels follow the selected website language', () => {
  const metric = (metricId, metricKey, value, unit, currency = null) => ({
    metric_id: metricId,
    metric_key: metricKey,
    value,
    unit,
    currency,
    provider: 'SEC EDGAR',
    source_concept: `us-gaap:${metricKey}`,
    source_document: 'https://sec.example/filing',
    period_end: '2026-06-30',
    verification_status: 'OFFICIAL',
  })
  const context = buildAssistantReportContext({
    overview: {
      ticker: 'MSFT',
      name: 'Microsoft Corporation',
    },
    financials: {
      metrics: [
        metric('market-cap', 'market_cap', 3_700_000_000_000, 'currency', 'USD'),
        metric('trailing-pe', 'trailing_pe', 31.4, 'multiple'),
      ],
      verification_results: [
        { verification_result_id: 'market-cap-result', metric_key: 'market_cap', selected_metric_id: 'market-cap', verification_status: 'OFFICIAL' },
        { verification_result_id: 'trailing-pe-result', metric_key: 'trailing_pe', selected_metric_id: 'trailing-pe', verification_status: 'OFFICIAL' },
      ],
    },
  }, null, 'zh')

  assert.deepEqual(context.evidence.map((item) => item.label), ['市值', '历史市盈率'])
  assert.equal(context.evidence[1].value, '31.4 multiple')
})
