import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../context/LanguageContext.jsx'
import { api } from '../lib/api.js'
import InvestmentPolicyBuilder from './InvestmentPolicyBuilder.jsx'

vi.mock('../lib/api.js', () => ({
  api: {
    investmentPolicies: {
      extract: vi.fn(),
      confirm: vi.fn(),
    },
  },
}))

const families = {
  principles: [],
  market_scopes: [],
  sector_preferences: [],
  theme_preferences: [],
  metric_rules: [],
  constraints: [],
  valuation_rules: [],
  portfolio_rules: [],
  alert_rules: [],
}

const rule = {
  rule_type: 'excluded_tickers',
  operator: 'not_in',
  value: ['TSLA'],
  importance: 5,
  hard_or_soft: 'hard',
  rationale: 'The user explicitly excluded TSLA.',
  enabled: true,
  application_effect: 'filtering',
}

const proposal = {
  proposal_id: 'proposal-1',
  detected_languages: ['es', 'en'],
  requires_confirmation: true,
  ai_provider: 'Anthropic',
  created_at: '2026-07-23T12:00:00Z',
  proposed_policy: {
    name: 'Quality policy',
    description: 'Prefer quality and avoid TSLA.',
    initial_version: {
      status: 'draft',
      change_summary: 'AI-extracted proposal awaiting user confirmation',
      effective_at: null,
      ...families,
      constraints: [rule],
    },
  },
  issues: [{
    issue_id: 'issue-1',
    code: 'ambiguous_instruction',
    severity: 'warning',
    message: 'Quality was not defined.',
    source_text: 'quality companies',
    rule_families: ['principles'],
  }],
}

function renderBuilder() {
  return render(
    <LanguageProvider>
      <InvestmentPolicyBuilder
        open
        customerId="customer-1"
        onClose={vi.fn()}
        onRequireProfile={vi.fn()}
      />
    </LanguageProvider>,
  )
}

describe('InvestmentPolicyBuilder confirmation flow', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.clearAllMocks()
    api.investmentPolicies.extract.mockResolvedValue(proposal)
    api.investmentPolicies.confirm.mockResolvedValue({
      id: 'policy-1',
      name: 'Quality policy',
      published_version_number: 1,
    })
  })

  afterEach(() => {
    cleanup()
    document.body.style.overflow = ''
  })

  it('shows every rule family and saves only after review and explicit confirmation', async () => {
    const user = userEvent.setup()
    renderBuilder()

    await user.type(
      screen.getByLabelText('Describe your investment preferences'),
      'Quiero quality companies but avoid TSLA.',
    )
    await user.click(screen.getByRole('button', { name: 'Interpret preferences' }))

    expect(api.investmentPolicies.extract).toHaveBeenCalledWith(
      'customer-1',
      {
        preferences: 'Quiero quality companies but avoid TSLA.',
        language_hint: 'en',
      },
    )
    expect(await screen.findByRole('heading', {
      name: 'Review every interpreted rule.',
    })).toBeTruthy()

    for (const heading of [
      'Principles',
      'Markets',
      'Sectors',
      'Themes',
      'Metrics',
      'Constraints',
      'Valuation preferences',
      'Portfolio rules',
      'Alerts',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeTruthy()
    }
    expect(screen.getByDisplayValue('["TSLA"]')).toBeTruthy()
    expect(screen.getByText('Quality was not defined.')).toBeTruthy()

    const confirmButton = screen.getByRole('button', {
      name: 'Confirm and activate policy',
    })
    expect(confirmButton).toHaveProperty('disabled', true)

    await user.click(screen.getByText('Quality was not defined.'))
    await user.click(screen.getByText(
      'I reviewed every rule and explicitly confirm this policy.',
    ))
    expect(confirmButton).toHaveProperty('disabled', false)
    await user.click(confirmButton)

    await waitFor(() => expect(api.investmentPolicies.confirm).toHaveBeenCalled())
    const [, , confirmation] = api.investmentPolicies.confirm.mock.calls[0]
    expect(confirmation.confirmed).toBe(true)
    expect(confirmation.acknowledged_issue_ids).toEqual(['issue-1'])
    expect(confirmation.policy.initial_version.status).toBe('draft')
    expect(confirmation.policy.initial_version.constraints[0].value).toEqual(['TSLA'])
    expect(await screen.findByText('Your policy is active and versioned.')).toBeTruthy()
  })

  it('allows users to edit interpreted rules before confirming', async () => {
    const user = userEvent.setup()
    renderBuilder()
    await user.type(
      screen.getByLabelText('Describe your investment preferences'),
      'Avoid TSLA.',
    )
    await user.click(screen.getByRole('button', { name: 'Interpret preferences' }))
    await screen.findByRole('heading', { name: 'Constraints' })

    const constraints = screen.getByRole('heading', {
      name: 'Constraints',
    }).closest('section')
    const valueInput = within(constraints).getByLabelText('Value')
    fireEvent.change(valueInput, { target: { value: '["TSLA","COIN"]' } })
    expect(valueInput).toHaveProperty('value', '["TSLA","COIN"]')
  })
})
