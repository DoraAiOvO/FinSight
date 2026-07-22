import { useEffect, useRef, useState } from 'react'
import LanguageSwitcher from './LanguageSwitcher.jsx'
import { useCustomerProfile } from '../context/CustomerProfileContext.jsx'
import { LANGUAGE_OPTIONS, useLanguage } from '../context/LanguageContext.jsx'
import { useTranslation } from '../hooks/useTranslation.js'
import {
  EXPERIENCE_OPTIONS,
  HORIZON_OPTIONS,
  INDUSTRY_OPTIONS,
  PRIORITY_OPTIONS,
  REPORT_DEPTH_OPTIONS,
  RISK_OPTIONS,
  defaultProfile,
  profilePayload,
  toggleSelection,
} from '../lib/customerProfile.js'
import { readStoredLanguage } from '../lib/language.js'

const EXPERIENCE_KEYS = {
  beginner: 'profileExperienceBeginner',
  intermediate: 'profileExperienceIntermediate',
  advanced: 'profileExperienceAdvanced',
}
const HORIZON_KEYS = {
  short_term: 'profileHorizonShort',
  one_to_three_years: 'profileHorizonMedium',
  five_plus_years: 'profileHorizonLong',
}
const PRIORITY_KEYS = {
  growth: 'profilePriorityGrowth',
  stability: 'profilePriorityStability',
  income: 'profilePriorityIncome',
  value: 'profilePriorityValue',
  innovation: 'profilePriorityInnovation',
}
const RISK_KEYS = {
  low: 'profileRiskLow',
  medium: 'profileRiskMedium',
  high: 'profileRiskHigh',
}
const DEPTH_KEYS = {
  quick: 'profileDepthQuick',
  standard: 'profileDepthStandard',
  deep: 'profileDepthDeep',
}
const INDUSTRY_KEYS = {
  Technology: 'industryTechnology',
  'Financial Services': 'industryFinancialServices',
  Healthcare: 'industryHealthcare',
  'Consumer Cyclical': 'industryConsumerCyclical',
  Industrials: 'industryIndustrials',
  Energy: 'industryEnergy',
  'Real Estate': 'industryRealEstate',
  'Communication Services': 'industryCommunicationServices',
  Utilities: 'industryUtilities',
  'Basic Materials': 'industryBasicMaterials',
}
const STEP_TITLES = ['profileStepOne', 'profileStepTwo', 'profileStepThree']

function ChoiceGroup({ legend, name, options, value, labelKeys, onChange }) {
  const { t } = useTranslation()
  return (
    <fieldset className="profile-fieldset">
      <legend>{t(legend)}</legend>
      <div className="profile-choice-grid">
        {options.map((option) => (
          <label className={value === option ? 'profile-choice selected' : 'profile-choice'} key={option}>
            <input
              type="radio"
              name={name}
              value={option}
              checked={value === option}
              onChange={() => onChange(option)}
            />
            <span>{t(labelKeys[option])}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function MultiChoiceGroup({ legend, hint, options, values, labelKeys, maximum, onChange }) {
  const { t } = useTranslation()
  return (
    <fieldset className="profile-fieldset">
      <legend>{t(legend)}</legend>
      {hint && <p className="profile-field-hint">{t(hint)}</p>}
      <div className="profile-choice-grid multi">
        {options.map((option) => {
          const selected = values.includes(option)
          const disabled = !selected && values.length >= maximum
          return (
            <label className={selected ? 'profile-choice selected' : 'profile-choice'} key={option}>
              <input
                type="checkbox"
                value={option}
                checked={selected}
                disabled={disabled}
                onChange={() => onChange(toggleSelection(values, option, maximum))}
              />
              <span>{t(labelKeys[option])}</span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

function LanguageChoices({ legend, value, onChange }) {
  const { t } = useTranslation()
  return (
    <fieldset className="profile-fieldset">
      <legend>{t(legend)}</legend>
      <div className="profile-choice-grid language-grid">
        {LANGUAGE_OPTIONS.map((option) => (
          <label className={value === option.code ? 'profile-choice selected' : 'profile-choice'} key={option.code}>
            <input
              type="radio"
              name="language"
              value={option.code}
              checked={value === option.code}
              onChange={() => onChange(option.code)}
            />
            <span>{option.name}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function isFirstLanguageVisit(profile) {
  if (profile || typeof window === 'undefined') return false
  return !readStoredLanguage(window.localStorage)
}

export default function CustomerOnboarding() {
  const { t, language } = useTranslation()
  const { setLanguage } = useLanguage()
  const {
    profile,
    onboardingOpen,
    closeOnboarding,
    saveProfile,
  } = useCustomerProfile()
  const [step, setStep] = useState(0)
  const [values, setValues] = useState(() => defaultProfile(language))
  const [languageWelcome, setLanguageWelcome] = useState(() => isFirstLanguageVisit(profile))
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const dialogRef = useRef(null)
  const previouslyFocused = useRef(null)
  const wasOpen = useRef(false)

  useEffect(() => {
    if (!onboardingOpen) {
      wasOpen.current = false
      return
    }
    if (wasOpen.current) return
    wasOpen.current = true
    const initialValues = profile ? profilePayload(profile) : defaultProfile(language)
    const showLanguageWelcome = isFirstLanguageVisit(profile)
    setValues(initialValues)
    setLanguage(initialValues.preferred_language)
    setLanguageWelcome(showLanguageWelcome)
    setStep(0)
    setError(null)
  }, [onboardingOpen, profile, language, setLanguage])

  useEffect(() => {
    if (!onboardingOpen) return undefined
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [onboardingOpen])

  useEffect(() => {
    if (!onboardingOpen) return undefined
    previouslyFocused.current = document.activeElement
    dialogRef.current?.focus()
    return () => {
      if (previouslyFocused.current instanceof HTMLElement) previouslyFocused.current.focus()
    }
  }, [onboardingOpen])

  if (!onboardingOpen) return null

  const setValue = (key, value) => setValues((current) => ({ ...current, [key]: value }))
  const setPreferredLanguage = (nextLanguage) => {
    setValue('preferred_language', nextLanguage)
    setLanguage(nextLanguage)
  }
  const currentStep = t('profileStep')
    .replace('{current}', String(step + 1))
    .replace('{total}', '3')

  function nextStep() {
    if (step === 1 && values.priorities.length === 0) {
      setError(t('profileRequired'))
      return
    }
    setError(null)
    setStep((current) => Math.min(2, current + 1))
  }

  function handleDialogKeyDown(event) {
    if (event.key === 'Escape' && !saving) {
      event.preventDefault()
      closeOnboarding()
      return
    }
    if (event.key !== 'Tab') return

    const focusable = [...dialogRef.current.querySelectorAll(
      'button:not([disabled]), select:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
    )].filter((element) => !element.closest('[hidden]'))
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  async function submit(event) {
    event.preventDefault()
    if (values.industries_of_interest.length === 0) {
      setError(t('profileRequired'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      await saveProfile(values)
    } catch {
      setError(t('profileSaveError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="profile-overlay" role="presentation">
      <section
        className="profile-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-title"
        aria-describedby="profile-intro"
        lang={language}
        onKeyDown={handleDialogKeyDown}
        ref={dialogRef}
        tabIndex="-1"
      >
        <div className="profile-dialog-head">
          <div>
            <p className="eyebrow">{t('profileSetupKicker')}</p>
            <h2 id="profile-title">
              {t(languageWelcome ? 'profileLanguageWelcomeTitle' : profile ? 'profileEditTitle' : 'profileSetupTitle')}
            </h2>
          </div>
          <div className="profile-dialog-tools">
            <LanguageSwitcher
              compact
              id="onboarding-language"
              value={values.preferred_language}
              onChange={setPreferredLanguage}
            />
            {profile && (
              <button className="profile-close" type="button" onClick={closeOnboarding} aria-label={t('profileClose')}>×</button>
            )}
          </div>
        </div>
        <p className="profile-intro" id="profile-intro">
          {t(languageWelcome ? 'profileLanguageWelcomeText' : 'profileIntro')}
        </p>

        {languageWelcome ? (
          <div className="profile-language-welcome">
            <LanguageChoices
              legend="profileLanguageSelection"
              value={values.preferred_language}
              onChange={setPreferredLanguage}
            />
            <div className="profile-actions">
              <button type="button" className="profile-secondary" onClick={closeOnboarding}>
                {t('profileSkip')}
              </button>
              <button type="button" className="profile-primary" onClick={() => setLanguageWelcome(false)}>
                {t('profileLanguageContinue')}
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="profile-progress" aria-label={currentStep}>
              {[0, 1, 2].map((index) => <span className={index <= step ? 'active' : ''} key={index} />)}
            </div>
            <div className="profile-step-heading">
              <span>{currentStep}</span>
              <strong>{t(STEP_TITLES[step])}</strong>
            </div>

            <form onSubmit={submit}>
          {step === 0 && (
            <div className="profile-step">
              <ChoiceGroup
                legend="profileExperienceQuestion"
                name="experience"
                options={EXPERIENCE_OPTIONS}
                value={values.experience_level}
                labelKeys={EXPERIENCE_KEYS}
                onChange={(value) => setValue('experience_level', value)}
              />
              <ChoiceGroup
                legend="profileHorizonQuestion"
                name="horizon"
                options={HORIZON_OPTIONS}
                value={values.research_horizon}
                labelKeys={HORIZON_KEYS}
                onChange={(value) => setValue('research_horizon', value)}
              />
            </div>
          )}

          {step === 1 && (
            <div className="profile-step">
              <MultiChoiceGroup
                legend="profilePrioritiesQuestion"
                hint="profilePrioritiesHint"
                options={PRIORITY_OPTIONS}
                values={values.priorities}
                labelKeys={PRIORITY_KEYS}
                maximum={5}
                onChange={(value) => setValue('priorities', value)}
              />
              <ChoiceGroup
                legend="profileRiskQuestion"
                name="risk"
                options={RISK_OPTIONS}
                value={values.risk_comfort}
                labelKeys={RISK_KEYS}
                onChange={(value) => setValue('risk_comfort', value)}
              />
              <p className="profile-risk-note">{t('profileRiskNote')}</p>
            </div>
          )}

          {step === 2 && (
            <div className="profile-step">
              <ChoiceGroup
                legend="profileDepthQuestion"
                name="depth"
                options={REPORT_DEPTH_OPTIONS}
                value={values.preferred_report_depth}
                labelKeys={DEPTH_KEYS}
                onChange={(value) => setValue('preferred_report_depth', value)}
              />
              <LanguageChoices
                legend="profileLanguageQuestion"
                value={values.preferred_language}
                onChange={setPreferredLanguage}
              />
              <MultiChoiceGroup
                legend="profileIndustriesQuestion"
                hint="profileIndustriesHint"
                options={INDUSTRY_OPTIONS}
                values={values.industries_of_interest}
                labelKeys={INDUSTRY_KEYS}
                maximum={8}
                onChange={(value) => setValue('industries_of_interest', value)}
              />
            </div>
          )}

          {error && <p className="profile-error" role="alert">{error}</p>}

          <aside className="profile-safety">
            <strong>{t('profileSafetyTitle')}</strong>
            <span>{t('profileSafetyText')}</span>
          </aside>

          <div className="profile-actions">
            <div>
              {step > 0 ? (
                <button type="button" className="profile-secondary" onClick={() => { setStep(step - 1); setError(null) }}>
                  {t('profileBack')}
                </button>
              ) : !profile ? (
                <button type="button" className="profile-secondary" onClick={closeOnboarding}>
                  {t('profileSkip')}
                </button>
              ) : null}
            </div>
            {step < 2 ? (
              <button type="button" className="profile-primary" onClick={nextStep}>{t('profileNext')}</button>
            ) : (
              <button type="submit" className="profile-primary" disabled={saving}>
                {saving ? t('profileSaving') : t('profileSave')}
              </button>
            )}
          </div>
            </form>
          </>
        )}
      </section>
    </div>
  )
}
