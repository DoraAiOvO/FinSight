import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../context/LanguageContext.jsx'
import { api } from '../lib/api.js'
import AssistantWidget from './AssistantWidget.jsx'

vi.mock('../lib/api.js', () => ({
  api: { assistant: { chat: vi.fn() } },
}))

function setOnline(value) {
  Object.defineProperty(window.navigator, 'onLine', { configurable: true, value })
}

function renderWidget(props = {}) {
  return render(
    <LanguageProvider>
      <AssistantWidget {...props} />
    </LanguageProvider>,
  )
}

describe('AssistantWidget', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setOnline(true)
    vi.clearAllMocks()
  })

  afterEach(() => cleanup())

  it('opens accessibly and greets in the selected website language', async () => {
    window.localStorage.setItem('language', 'zh')
    const user = userEvent.setup()
    renderWidget()

    const trigger = screen.getByRole('button', { name: '打开 FinSight 助手' })
    await user.click(trigger)

    expect(screen.getByRole('dialog', { name: 'FinSight 助手' })).toBeTruthy()
    expect(screen.getByText(/P\/E 是什么/)).toBeTruthy()
    expect(screen.getByText(/你好！我可以解释金融概念/)).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('textbox'))

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(document.activeElement).toBe(trigger))
  })

  it('keeps session history, sends current report evidence, and renders citations', async () => {
    api.assistant.chat.mockResolvedValue({
      reply: 'The report shows a trailing P/E of 31.4x. [1]',
      intent: 'CURRENT_REPORT_QUESTION',
      citations: [{
        evidence_id: 'overview.trailing_pe', title: 'Trailing P/E',
        source: 'Yahoo Finance', as_of_date: '2026-07-21', source_url: 'https://example.com',
      }],
    })
    const currentReport = {
      ticker: 'MSFT', company_name: 'Microsoft Corporation',
      evidence: [{ evidence_id: 'overview.trailing_pe', label: 'Trailing P/E', value: '31.4x', source: 'Yahoo Finance' }],
    }
    const user = userEvent.setup()
    renderWidget({ customerId: 'customer-1', currentReport })

    await user.click(screen.getByRole('button', { name: 'Open FinSight Assistant' }))
    await user.click(screen.getByRole('button', { name: 'Explain this report simply.' }))

    await waitFor(() => expect(api.assistant.chat).toHaveBeenCalledTimes(1))
    const payload = api.assistant.chat.mock.calls[0][0]
    expect(payload.current_report).toEqual(currentReport)
    expect(payload.customer_id).toBe('customer-1')
    expect(payload.history[0].content).toMatch(/^Hi/)
    expect(await screen.findByText(/trailing P\/E of 31.4x/)).toBeTruthy()
    expect(screen.getByText('Evidence · 1')).toBeTruthy()
  })

  it('shows retry and offline states without losing the user message', async () => {
    api.assistant.chat
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({ reply: 'P/E explained.', intent: 'FINANCIAL_CONCEPT', citations: [] })
    const user = userEvent.setup()
    renderWidget()

    await user.click(screen.getByRole('button', { name: 'Open FinSight Assistant' }))
    const input = screen.getByRole('textbox')
    await user.type(input, 'What does P/E mean?')
    await user.keyboard('{Enter}')

    expect((await screen.findByRole('alert')).textContent).toContain("I couldn’t reach the assistant")
    expect(screen.getByText('What does P/E mean?')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('P/E explained.')).toBeTruthy()

    fireEvent.offline(window)
    expect(await screen.findByText(/You’re offline/)).toBeTruthy()
    expect(screen.getByRole('textbox')).toHaveProperty('disabled', true)
  })
})
