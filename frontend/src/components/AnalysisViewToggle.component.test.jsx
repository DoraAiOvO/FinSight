import { useState } from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { AnalysisViewToggle } from '../App.jsx'
import { LanguageProvider } from '../context/LanguageContext.jsx'

function ToggleFixture() {
  const [view, setView] = useState('personalized')
  return (
    <LanguageProvider>
      <AnalysisViewToggle value={view} onChange={setView} />
      <output>{view}</output>
    </LanguageProvider>
  )
}

describe('analysis view toggle', () => {
  afterEach(cleanup)

  it('switches explicitly between personalized and neutral evidence views', async () => {
    const user = userEvent.setup()
    render(<ToggleFixture />)

    const personalized = screen.getByRole('button', { name: 'Personalized View' })
    const neutral = screen.getByRole('button', { name: 'Neutral Evidence View' })
    expect(personalized.getAttribute('aria-pressed')).toBe('true')

    await user.click(neutral)
    expect(neutral.getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('neutral')).toBeTruthy()

    await user.click(personalized)
    expect(personalized.getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('personalized')).toBeTruthy()
  })
})
