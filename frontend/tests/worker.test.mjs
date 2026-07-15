import assert from 'node:assert/strict'
import test from 'node:test'

import worker, { buildInsights, buildOverview, normalizeTicker } from '../worker/index.js'

function series(type, values) {
  return {
    meta: { symbol: ['TEST'], type: [type] },
    [type]: values.map((raw, index) => ({
      asOfDate: `2026-0${index + 1}-31`,
      reportedValue: { raw },
    })),
  }
}

test('normalizes safe tickers and rejects malformed input', () => {
  assert.equal(normalizeTicker(' brk-b '), 'BRK-B')
  assert.throws(() => normalizeTicker('AAPL/MSFT'), /valid ticker/)
})

test('builds normalized overview metrics from Yahoo payloads', () => {
  const chart = {
    meta: {
      regularMarketPrice: 200,
      previousClose: 198,
      currency: 'USD',
      longName: 'Test Corp',
      fiftyTwoWeekLow: 120,
      fiftyTwoWeekHigh: 220,
    },
  }
  const fundamentals = [
    series('trailingMarketCap', [100e9]),
    series('trailingPeRatio', [25]),
    series('trailingTotalRevenue', [10e9]),
    series('trailingNetIncome', [2.5e9]),
    series('trailingOperatingIncome', [3e9]),
    series('quarterlyTotalRevenue', [1e9, 1.1e9, 1.2e9, 1.3e9, 1.25e9]),
    series('quarterlyTotalDebt', [5e9]),
    series('quarterlyStockholdersEquity', [10e9]),
    series('annualCashDividendsPaid', [-500e6]),
    series('annualBasicAverageShares', [1e9]),
  ]

  const overview = buildOverview('TEST', chart, fundamentals)
  assert.equal(overview.name, 'Test Corp')
  assert.equal(overview.profit_margin, 0.25)
  assert.equal(overview.operating_margin, 0.3)
  assert.equal(overview.revenue_growth, 0.25)
  assert.equal(overview.debt_to_equity, 50)
  assert.equal(overview.dividend_yield, 0.0025)
})

test('keeps analysis conclusions tied to visible evidence', () => {
  const insights = buildInsights({
    trailing_pe: 65,
    revenue_growth: 0.35,
    price: 150,
    fifty_two_week_low: 100,
    fifty_two_week_high: 200,
  })
  const valuation = insights.find((insight) => insight.title === 'Rich valuation')
  assert.equal(valuation.evidence[0].value, '65.0')
  assert.ok(insights.some((insight) => insight.title === 'Fast revenue growth'))
})

test('serves edge runtime health without external requests', async () => {
  const response = await worker.fetch(new Request('https://finsight.test/api/health'), {})
  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), { status: 'ok', ai_enabled: false, runtime: 'edge' })
})
