import { LanguageProvider } from '../context/LanguageContext.jsx'
import { api } from '../lib/api.js'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SearchBar from './SearchBar.jsx'

vi.mock('../lib/api.js', () => ({
  api: { searchCompanies: vi.fn() },
}))

function company(overrides = {}) {
  return {
    ticker: 'MSFT',
    company_name: 'Microsoft Corporation',
    exchange: 'Nasdaq',
    country: 'United States',
    sector: 'Technology',
    asset_type: 'equity',
    match_score: 0.98,
    match_type: 'exact_name',
    data_source: 'FinSight maintained symbol index',
    matched_text: 'Microsoft Corporation',
    ...overrides,
  }
}

function renderSearch(overrides = {}) {
  const props = {
    mode: 'analyze',
    onModeChange: vi.fn(),
    onAnalyze: vi.fn(),
    onCompare: vi.fn(),
    loading: false,
    ...overrides,
  }
  return {
    ...render(<LanguageProvider><SearchBar {...props} /></LanguageProvider>),
    props,
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('company autocomplete search', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem('language', 'en')
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('debounces results, exposes combobox semantics, and selects with the keyboard', async () => {
    api.searchCompanies.mockResolvedValue([company({
      match_type: 'fuzzy',
      match_score: 0.84,
      matched_text: 'microsoft',
    })])
    const user = userEvent.setup()
    const { props } = renderSearch()
    const input = screen.getByRole('combobox', { name: 'Research a public company' })

    await user.type(input, 'microsft')
    expect(screen.getAllByText('Searching companies…')).toHaveLength(2)
    await waitFor(() => expect(api.searchCompanies).toHaveBeenCalledTimes(1))

    const option = await screen.findByRole('option', { name: /Microsoft Corporation MSFT/ })
    expect(option.textContent).toContain('Nasdaq')
    expect(option.textContent).toContain('Technology')
    expect(option.textContent).toContain('Close spelling match')
    expect(screen.getByText(/Did you mean/)).toBeTruthy()
    expect(input.getAttribute('aria-expanded')).toBe('true')

    await user.keyboard('{ArrowDown}')
    expect(input.getAttribute('aria-activedescendant')).toBe(option.id)
    await user.keyboard('{Enter}')
    expect(input).toHaveProperty('value', 'Microsoft Corporation · MSFT')

    await user.click(screen.getByRole('button', { name: /Build research brief/ }))
    expect(props.onAnalyze).toHaveBeenCalledWith('MSFT')
  })

  it('does not auto-submit a fuzzy low-confidence name but preserves direct ticker entry', async () => {
    api.searchCompanies.mockResolvedValue([company({
      match_type: 'fuzzy',
      match_score: 0.84,
      matched_text: 'microsoft',
    })])
    const user = userEvent.setup()
    const { props } = renderSearch()
    const input = screen.getByRole('combobox')

    await user.type(input, 'microsft')
    await screen.findByRole('option')
    await user.click(screen.getByRole('button', { name: /Build research brief/ }))
    expect(props.onAnalyze).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toContain('Select a company')

    await user.clear(input)
    await user.type(input, 'MSFT')
    await user.click(screen.getByRole('button', { name: /Build research brief/ }))
    expect(props.onAnalyze).toHaveBeenCalledWith('MSFT')
  })

  it('prevents an older autocomplete response from replacing a newer one', async () => {
    const appleRequest = deferred()
    const microsoftRequest = deferred()
    api.searchCompanies.mockImplementation((query) => (
      query === 'Apple' ? appleRequest.promise : microsoftRequest.promise
    ))
    renderSearch()
    const input = screen.getByRole('combobox')

    fireEvent.change(input, { target: { value: 'Apple' } })
    await waitFor(() => expect(api.searchCompanies).toHaveBeenCalledTimes(1))
    fireEvent.change(input, { target: { value: 'Microsoft' } })
    await waitFor(() => expect(api.searchCompanies).toHaveBeenCalledTimes(2))

    await act(async () => {
      microsoftRequest.resolve([company()])
      await microsoftRequest.promise
    })
    expect(await screen.findByRole('option', { name: /Microsoft Corporation/ })).toBeTruthy()

    await act(async () => {
      appleRequest.resolve([company({ ticker: 'AAPL', company_name: 'Apple Inc.' })])
      await appleRequest.promise
    })
    expect(screen.queryByRole('option', { name: /Apple Inc/ })).toBeNull()
    expect(screen.getByRole('option', { name: /Microsoft Corporation/ })).toBeTruthy()
  })

  it('uses removable company chips and submits two to five compare selections', async () => {
    api.searchCompanies.mockImplementation((query) => Promise.resolve([
      query.startsWith('Apple')
        ? company({ ticker: 'AAPL', company_name: 'Apple Inc.', matched_text: 'Apple Inc.' })
        : company(),
    ]))
    const user = userEvent.setup()
    const { props } = renderSearch({ mode: 'compare' })
    const input = screen.getByRole('combobox')

    await user.type(input, 'Apple')
    await user.click(await screen.findByRole('option', { name: /Apple Inc. AAPL/ }))
    await user.type(input, 'Microsoft')
    await screen.findByRole('option', { name: /Microsoft Corporation MSFT/ })
    await user.keyboard('{ArrowDown}{Enter}')

    const removeApple = screen.getByRole('button', { name: 'Remove Apple Inc.' })
    expect(removeApple).toBeTruthy()
    await user.click(removeApple)
    expect(screen.queryByRole('button', { name: 'Remove Apple Inc.' })).toBeNull()

    await user.type(input, 'AAPL')
    await user.keyboard('{Enter}')
    await user.click(screen.getByRole('button', { name: /Compare companies/ }))
    expect(props.onCompare).toHaveBeenCalledWith(['MSFT', 'AAPL'])
  })

  it('renders translated empty and provider-error states', async () => {
    api.searchCompanies.mockResolvedValueOnce([]).mockRejectedValueOnce(new Error('down'))
    const user = userEvent.setup()
    renderSearch()
    const input = screen.getByRole('combobox')

    await user.type(input, 'unsupported')
    expect(await screen.findAllByText(/No supported companies found/)).toHaveLength(2)
    await user.clear(input)
    await user.type(input, 'another')
    expect(await screen.findAllByText(/Company search is temporarily unavailable/)).toHaveLength(2)
  })
})
