import assert from 'node:assert/strict'
import test from 'node:test'

import { valuationFormValues, valuationRequest } from './valuation.js'


function point(value) {
  return { value }
}


test('valuation form round-trips API ratios as editable percentages', () => {
  const form = valuationFormValues({
    base_case: {
      assumptions: {
        projection_years: 5,
        revenue_growth: point(0.08),
        free_cash_flow_margin: point(0.12),
        discount_rate: point(0.105),
        terminal_growth: point(0.025),
        annual_share_dilution: point(0.01),
      },
    },
  })

  assert.deepEqual(valuationRequest(form), {
    projection_years: 5,
    revenue_growth: 0.08,
    free_cash_flow_margin: 0.12,
    discount_rate: 0.105,
    terminal_growth: 0.025,
    annual_share_dilution: 0.01,
  })
})


test('valuation request rejects a terminal rate at or above the discount rate', () => {
  assert.throws(
    () => valuationRequest({
      projection_years: '5',
      revenue_growth: '8',
      free_cash_flow_margin: '12',
      discount_rate: '2',
      terminal_growth: '3',
      annual_share_dilution: '0',
    }),
    /discount_terminal_spread/,
  )
})
