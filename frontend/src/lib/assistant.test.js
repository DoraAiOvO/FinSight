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
  const point = {
    value: 31.4,
    display_value: '31.4x',
    provider: 'Example',
    source: 'Fixture',
    as_of_date: '2026-07-21',
  }
  const context = buildAssistantReportContext({
    overview: {
      ticker: 'MSFT',
      name: 'Microsoft Corporation',
      trailing_pe: point,
      market_cap: { ...point, display_value: '3.7万亿美元' },
    },
  }, null, 'zh')

  assert.deepEqual(context.evidence.map((item) => item.label), ['市值', '历史市盈率'])
  assert.equal(context.evidence[1].value, '31.4x')
})
