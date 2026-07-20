import { useEffect, useState } from 'react'
import { useCustomerProfile } from '../context/CustomerProfileContext.jsx'
import { LANGUAGE_OPTIONS } from '../context/LanguageContext.jsx'
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

export default function CustomerOnboarding() {
  const { t, language } = useTranslation()
  const {
    profile,
    onboardingOpen,
    closeOnboarding,
    saveProfile,
  } = useCustomerProfile()
  const [step, setStep] = useState(0)
  const [values, setValues] = useState(() => defaultProfile(language))
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!onboardingOpen) return
    setValues(profile ? profilePayload(profile) : defaultProfile(language))
    setStep(0)
    setError(null)
  }, [onboardingOpen, profile, language])

  useEffect(() => {
    if (!onboardingOpen) return undefined
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [onboardingOpen])

  if (!onboardingOpen) return null

  const setValue = (key, value) => setValues((current) => ({ ...current, [key]: value }))
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
      <section className="profile-dialog" role="dialog" aria-modal="true" aria-labelledby="profile-title">
        <div className="profile-dialog-head">
          <div>
            <p className="eyebrow">{t('profileSetupKicker')}</p>
            <h2 id="profile-title">{t(profile ? 'profileEditTitle' : 'profileSetupTitle')}</h2>
          </div>
          {profile && (
            <button className="profile-close" type="button" onClick={closeOnboarding} aria-label={t('profileClose')}>×</button>
          )}
        </div>
        <p className="profile-intro">{t('profileIntro')}</p>

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
              <fieldset className="profile-fieldset">
                <legend>{t('profileLanguageQuestion')}</legend>
                <div className="profile-choice-grid language-grid">
                  {LANGUAGE_OPTIONS.map((option) => (
                    <label className={values.preferred_language === option.code ? 'profile-choice selected' : 'profile-choice'} key={option.code}>
                      <input
                        type="radio"
                        name="language"
                        value={option.code}
                        checked={values.preferred_language === option.code}
                        onChange={() => setValue('preferred_language', option.code)}
                      />
                      <span>{option.name}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
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
      </section>
    </div>
  )
}
