import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import FinancialVerificationPanel from './FinancialVerificationPanel.jsx'

vi.mock('../hooks/useTranslation.js', () => ({
  useTranslation: () => ({ t: (key) => key, locale: 'en-US' }),
}))

const evidence = {
  metrics: [{
    metric_id: 'revenue-sec',
    metric_key: 'total_revenue',
    value: 1000,
    unit: 'currency',
    currency: 'USD',
    provider: 'SEC EDGAR',
    source_document: 'https://sec.example/filing',
    source_concept: 'us-gaap:Revenue',
    period_type: 'ANNUAL',
    period_end: '2025-12-31',
    fiscal_year: 2025,
    fiscal_quarter: null,
    filing_date: '2026-02-15',
    calculation_formula: 'net_income / total_revenue',
  }],
  verification_results: [{
    verification_result_id: 'revenue-result',
    metric_key: 'total_revenue',
    selected_metric_id: 'revenue-sec',
    verification_status: 'CONFLICTING',
    explanation: 'Sources disagree.',
  }],
  conflicts: [{
    conflict_id: 'revenue-conflict',
    metric_key: 'total_revenue',
    financial_period_id: 'period-2025',
    providers: ['SEC EDGAR', 'Yahoo Finance'],
    values: [1000, 1100],
    relative_difference: 0.09,
  }],
  missing_metric_keys: ['operating_cash_flow'],
  validation_failures: [],
}

describe('FinancialVerificationPanel', () => {
  it('shows source, period, status, formula, and preserved conflicts', () => {
    render(<FinancialVerificationPanel evidence={evidence} />)

    expect(screen.getByText('SEC EDGAR ↗')).toBeTruthy()
    expect(screen.getByText('FY2025')).toBeTruthy()
    expect(screen.getByText('CONFLICTING')).toBeTruthy()
    expect(screen.getByText('net_income / total_revenue')).toBeTruthy()
    expect(screen.getByText(/Yahoo Finance: 1,100/)).toBeTruthy()
  })
})
