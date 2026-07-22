import { CustomerProfileProvider, useCustomerProfile } from '../context/CustomerProfileContext.jsx'
import { LanguageProvider } from '../context/LanguageContext.jsx'
import { api } from '../lib/api.js'
import { defaultProfile } from '../lib/customerProfile.js'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CustomerOnboarding from './CustomerOnboarding.jsx'

vi.mock('../lib/api.js', () => ({
  api: {
    customerProfile: {
      create: vi.fn(),
      get: vi.fn(),
      update: vi.fn(),
    },
  },
}))

function setBrowserLanguages(...languages) {
  Object.defineProperty(window.navigator, 'languages', {
    configurable: true,
    value: languages,
  })
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: languages[0],
  })
}

function renderOnboarding(children = <CustomerOnboarding />) {
  return render(
    <LanguageProvider>
      <CustomerProfileProvider>
        {children}
      </CustomerProfileProvider>
    </LanguageProvider>,
  )
}

function ProfileFixture() {
  const { profile, openOnboarding } = useCustomerProfile()
  return (
    <>
      <button type="button" disabled={!profile} onClick={openOnboarding}>Open profile</button>
      <CustomerOnboarding />
    </>
  )
}

describe('CustomerOnboarding language experience', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setBrowserLanguages('en-US')
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
    document.body.style.overflow = ''
  })

  it('starts a first visit in Chinese for a Chinese browser locale', async () => {
    setBrowserLanguages('zh-CN', 'en-US')

    renderOnboarding()

    expect(await screen.findByRole('heading', { name: '选择你的语言。' })).toBeTruthy()
    expect(screen.getByText('在设置研究画像前请先选择语言。你随时都可以更改。')).toBeTruthy()
    expect(screen.getByRole('combobox')).toHaveProperty('value', 'zh')
    expect(document.documentElement.lang).toBe('zh')
  })

  it('translates immediately and synchronizes the profile when changed to Chinese', async () => {
    const user = userEvent.setup()
    renderOnboarding()

    expect(await screen.findByRole('heading', { name: 'Choose your language.' })).toBeTruthy()
    await user.selectOptions(screen.getByRole('combobox'), 'zh')

    expect(await screen.findByRole('heading', { name: '选择你的语言。' })).toBeTruthy()
    expect(screen.getByText('暂时跳过')).toBeTruthy()
    expect(document.documentElement.lang).toBe('zh')

    await user.click(screen.getByRole('button', { name: '继续设置研究画像' }))
    expect(await screen.findByRole('heading', { name: '让每一份报告都更容易使用。' })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: '继续' }))
    await user.click(screen.getByRole('button', { name: '继续' }))

    expect(screen.getByRole('radio', { name: '中文' })).toHaveProperty('checked', true)
  })

  it('restores a manually selected language after refresh', async () => {
    const user = userEvent.setup()
    const firstRender = renderOnboarding()
    await user.selectOptions(await screen.findByRole('combobox'), 'zh')
    expect(window.localStorage.getItem('language')).toBe('zh')

    firstRender.unmount()
    renderOnboarding()

    expect(await screen.findByRole('heading', { name: '让每一份报告都更容易使用。' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: '选择你的语言。' })).toBeNull()
    expect(screen.getByRole('combobox')).toHaveProperty('value', 'zh')
  })

  it('gives an authenticated profile preference priority and syncs the form', async () => {
    window.localStorage.setItem('finsight-customer-id', 'customer-1')
    window.localStorage.setItem('language', 'en')
    api.customerProfile.get.mockResolvedValue({
      ...defaultProfile('zh'),
      customer_id: 'customer-1',
      created_at: '2026-07-22T12:00:00Z',
      updated_at: '2026-07-22T12:00:00Z',
    })
    const user = userEvent.setup()

    renderOnboarding(<ProfileFixture />)
    const openButton = screen.getByRole('button', { name: 'Open profile' })
    await waitFor(() => expect(openButton).toHaveProperty('disabled', false))
    await waitFor(() => expect(document.documentElement.lang).toBe('zh'))
    await user.click(openButton)

    expect(await screen.findByRole('heading', { name: '更新你的研究画像。' })).toBeTruthy()
    expect(screen.getByRole('combobox')).toHaveProperty('value', 'zh')
    expect(window.localStorage.getItem('language')).toBe('zh')

    await user.click(screen.getByRole('button', { name: '继续' }))
    await user.click(screen.getByRole('button', { name: '继续' }))
    expect(screen.getByRole('radio', { name: '中文' })).toHaveProperty('checked', true)
  })

  it('keeps keyboard focus inside the dialog and supports Escape to skip', async () => {
    const user = userEvent.setup()
    renderOnboarding()
    const dialog = await screen.findByRole('dialog')

    expect(document.activeElement).toBe(dialog)
    await user.keyboard('{Shift>}{Tab}{/Shift}')
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Continue to research profile' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
