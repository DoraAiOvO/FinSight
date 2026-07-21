import { dataValue } from './api.js'


export const VALUATION_FIELDS = [
  { key: 'revenue_growth', labelKey: 'valuationRevenueGrowth', min: -50, max: 100, step: 0.5 },
  { key: 'free_cash_flow_margin', labelKey: 'valuationFcfMargin', min: -50, max: 80, step: 0.5 },
  { key: 'discount_rate', labelKey: 'valuationDiscountRate', min: 2, max: 50, step: 0.25 },
  { key: 'terminal_growth', labelKey: 'valuationTerminalGrowth', min: -5, max: 10, step: 0.25 },
  { key: 'annual_share_dilution', labelKey: 'valuationShareDilution', min: -10, max: 25, step: 0.25 },
]


function editablePercent(value) {
  const percent = Number(dataValue(value)) * 100
  return Number.isFinite(percent) ? String(Number(percent.toFixed(4))) : ''
}


export function valuationFormValues(valuation) {
  const assumptions = valuation?.base_case?.assumptions
  if (!assumptions) return null
  return {
    projection_years: String(assumptions.projection_years),
    ...Object.fromEntries(
      VALUATION_FIELDS.map(({ key }) => [key, editablePercent(assumptions[key])]),
    ),
  }
}


export function valuationRequest(form) {
  const projectionYears = Number(form.projection_years)
  if (!Number.isInteger(projectionYears) || projectionYears < 3 || projectionYears > 10) {
    throw new Error('projection_years')
  }
  const payload = { projection_years: projectionYears }
  VALUATION_FIELDS.forEach(({ key, min, max }) => {
    const percent = Number(form[key])
    if (!Number.isFinite(percent) || percent < min || percent > max) {
      throw new Error(key)
    }
    payload[key] = percent / 100
  })
  if (payload.discount_rate <= payload.terminal_growth) {
    throw new Error('discount_terminal_spread')
  }
  return payload
}
