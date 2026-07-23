import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'
import { api } from '../lib/api.js'

const LONG_TERM_TECH_VALUE_PRESET_ID = 'long-term-tech-value'

const RULE_GROUPS = [
  ['principles', 'policyPrinciples'],
  ['market_scopes', 'policyMarkets'],
  ['sector_preferences', 'policySectors'],
  ['theme_preferences', 'policyThemes'],
  ['metric_rules', 'policyMetrics'],
  ['constraints', 'policyConstraints'],
  ['valuation_rules', 'policyValuation'],
  ['portfolio_rules', 'policyPortfolio'],
  ['alert_rules', 'policyAlerts'],
]

const EFFECTS = [
  'preference_fit_scoring',
  'filtering',
  'ranking',
  'report_emphasis',
  'alerts',
]

const DEFAULT_EFFECT = {
  principles: 'report_emphasis',
  market_scopes: 'preference_fit_scoring',
  sector_preferences: 'ranking',
  theme_preferences: 'ranking',
  metric_rules: 'preference_fit_scoring',
  constraints: 'filtering',
  valuation_rules: 'preference_fit_scoring',
  portfolio_rules: 'preference_fit_scoring',
  alert_rules: 'alerts',
}

function valueText(value) {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function editablePolicy(policy) {
  return {
    ...policy,
    initial_version: {
      ...policy.initial_version,
      ...Object.fromEntries(RULE_GROUPS.map(([family]) => [
        family,
        policy.initial_version[family].map((rule) => ({
          ...rule,
          _valueText: valueText(rule.value),
        })),
      ])),
    },
  }
}

function parseValue(text) {
  const trimmed = text.trim()
  if (!trimmed) return ''
  try {
    return JSON.parse(trimmed)
  } catch {
    return text
  }
}

function submissionPolicy(policy) {
  return {
    name: policy.name,
    description: policy.description || null,
    initial_version: {
      status: 'draft',
      change_summary: policy.initial_version.change_summary,
      effective_at: null,
      ...Object.fromEntries(RULE_GROUPS.map(([family]) => [
        family,
        policy.initial_version[family].map(({ _valueText, ...rule }) => ({
          ...rule,
          value: parseValue(_valueText),
        })),
      ])),
    },
  }
}

function newRule(family, t) {
  return {
    rule_type: 'new_rule',
    operator: 'equals',
    value: '',
    _valueText: '',
    importance: 3,
    hard_or_soft: family === 'constraints' ? 'hard' : 'soft',
    rationale: t('policyAcknowledge'),
    enabled: true,
    application_effect: DEFAULT_EFFECT[family],
  }
}

function RuleEditor({ family, index, rule, onChange, onRemove }) {
  const { t } = useTranslation()
  const id = `policy-${family}-${index}`
  return (
    <article className="policy-rule">
      <div className="policy-rule-primary">
        <label htmlFor={`${id}-type`}>
          <span>{t('policyRuleType')}</span>
          <input
            id={`${id}-type`}
            value={rule.rule_type}
            onChange={(event) => onChange('rule_type', event.target.value)}
          />
        </label>
        <label htmlFor={`${id}-operator`}>
          <span>{t('policyOperator')}</span>
          <input
            id={`${id}-operator`}
            value={rule.operator}
            onChange={(event) => onChange('operator', event.target.value)}
          />
        </label>
        <label htmlFor={`${id}-value`}>
          <span>{t('policyValue')}</span>
          <input
            id={`${id}-value`}
            value={rule._valueText}
            onChange={(event) => onChange('_valueText', event.target.value)}
          />
        </label>
        <button
          type="button"
          className="policy-remove"
          onClick={onRemove}
          aria-label={`${t('policyRemoveRule')} ${index + 1}`}
        >
          ×
        </button>
      </div>
      <div className="policy-rule-options">
        <label htmlFor={`${id}-importance`}>
          <span>{t('policyImportance')}</span>
          <input
            id={`${id}-importance`}
            type="number"
            min="1"
            max="5"
            value={rule.importance}
            onChange={(event) => onChange('importance', Number(event.target.value))}
          />
        </label>
        <label htmlFor={`${id}-strength`}>
          <span>{t('policyStrength')}</span>
          <select
            id={`${id}-strength`}
            value={rule.hard_or_soft}
            onChange={(event) => onChange('hard_or_soft', event.target.value)}
          >
            <option value="soft">{t('policySoft')}</option>
            <option value="hard">{t('policyHard')}</option>
          </select>
        </label>
        <label htmlFor={`${id}-effect`}>
          <span>{t('policyEffect')}</span>
          <select
            id={`${id}-effect`}
            value={rule.application_effect}
            onChange={(event) => onChange('application_effect', event.target.value)}
          >
            {EFFECTS.map((effect) => <option value={effect} key={effect}>{effect}</option>)}
          </select>
        </label>
        <label className="policy-enabled" htmlFor={`${id}-enabled`}>
          <input
            id={`${id}-enabled`}
            type="checkbox"
            checked={rule.enabled}
            onChange={(event) => onChange('enabled', event.target.checked)}
          />
          <span>{t('policyEnabled')}</span>
        </label>
      </div>
      <label className="policy-rationale" htmlFor={`${id}-rationale`}>
        <span>{t('policyRationale')}</span>
        <textarea
          id={`${id}-rationale`}
          rows="2"
          value={rule.rationale}
          onChange={(event) => onChange('rationale', event.target.value)}
        />
      </label>
    </article>
  )
}

export default function InvestmentPolicyBuilder({
  open,
  customerId,
  onClose,
  onRequireProfile,
}) {
  const { t, language } = useTranslation()
  const dialogRef = useRef(null)
  const [screen, setScreen] = useState('describe')
  const [preferences, setPreferences] = useState('')
  const [proposal, setProposal] = useState(null)
  const [proposalSource, setProposalSource] = useState(null)
  const [policy, setPolicy] = useState(null)
  const [acknowledged, setAcknowledged] = useState({})
  const [makeDefault, setMakeDefault] = useState(true)
  const [explicitConfirmation, setExplicitConfirmation] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [loadingPreset, setLoadingPreset] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedPolicy, setSavedPolicy] = useState(null)
  const [error, setError] = useState(null)

  const allIssuesAcknowledged = useMemo(
    () => proposal?.issues.every((issue) => acknowledged[issue.issue_id]) ?? true,
    [acknowledged, proposal],
  )

  useEffect(() => {
    if (!open) return undefined
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    queueMicrotask(() => dialogRef.current?.focus())
    return () => { document.body.style.overflow = previousOverflow }
  }, [open])

  if (!open) return null

  function close() {
    if (extracting || loadingPreset || saving) return
    onClose()
    setScreen('describe')
    setPreferences('')
    setProposal(null)
    setProposalSource(null)
    setPolicy(null)
    setAcknowledged({})
    setMakeDefault(true)
    setExplicitConfirmation(false)
    setSavedPolicy(null)
    setError(null)
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') close()
  }

  async function extract(event) {
    event.preventDefault()
    if (!customerId) {
      onClose()
      onRequireProfile()
      return
    }
    setExtracting(true)
    setError(null)
    try {
      const result = await api.investmentPolicies.extract(customerId, {
        preferences,
        language_hint: language,
      })
      setProposal(result)
      setProposalSource('ai')
      setPolicy(editablePolicy(result.proposed_policy))
      setAcknowledged({})
      setMakeDefault(true)
      setExplicitConfirmation(false)
      setScreen('review')
    } catch (requestError) {
      setError(requestError.message || t('policyError'))
    } finally {
      setExtracting(false)
    }
  }

  async function useLongTermTechValuePreset() {
    if (!customerId) {
      onClose()
      onRequireProfile()
      return
    }
    setLoadingPreset(true)
    setError(null)
    try {
      const result = await api.investmentPolicies.fromPreset(
        customerId,
        LONG_TERM_TECH_VALUE_PRESET_ID,
      )
      setProposal(result)
      setProposalSource(LONG_TERM_TECH_VALUE_PRESET_ID)
      setPolicy(editablePolicy(result.proposed_policy))
      setAcknowledged({})
      setMakeDefault(false)
      setExplicitConfirmation(false)
      setScreen('review')
    } catch (requestError) {
      setError(requestError.message || t('policyError'))
    } finally {
      setLoadingPreset(false)
    }
  }

  function updateMetadata(field, value) {
    setPolicy((current) => ({ ...current, [field]: value }))
  }

  function updateRule(family, index, field, value) {
    setPolicy((current) => {
      const rules = current.initial_version[family].map((rule, ruleIndex) => (
        ruleIndex === index ? { ...rule, [field]: value } : rule
      ))
      return {
        ...current,
        initial_version: { ...current.initial_version, [family]: rules },
      }
    })
  }

  function removeRule(family, index) {
    setPolicy((current) => ({
      ...current,
      initial_version: {
        ...current.initial_version,
        [family]: current.initial_version[family].filter((_, ruleIndex) => ruleIndex !== index),
      },
    }))
  }

  function addRule(family) {
    setPolicy((current) => ({
      ...current,
      initial_version: {
        ...current.initial_version,
        [family]: [...current.initial_version[family], newRule(family, t)],
      },
    }))
  }

  async function confirm() {
    setSaving(true)
    setError(null)
    try {
      const stored = await api.investmentPolicies.confirm(
        customerId,
        proposal.proposal_id,
        {
          confirmed: true,
          policy: submissionPolicy(policy),
          make_default: makeDefault,
          acknowledged_issue_ids: proposal.issues
            .filter((issue) => acknowledged[issue.issue_id])
            .map((issue) => issue.issue_id),
        },
      )
      setSavedPolicy(stored)
      setScreen('saved')
    } catch (requestError) {
      setError(requestError.message || t('policyError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="profile-overlay policy-overlay" role="presentation">
      <section
        className="profile-dialog policy-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="policy-title"
        onKeyDown={handleKeyDown}
        ref={dialogRef}
        tabIndex="-1"
      >
        <div className="profile-dialog-head">
          <div>
            <p className="eyebrow">
              {screen === 'saved' ? t('policySavedKicker') : t('policyKicker')}
            </p>
            <h2 id="policy-title">
              {screen === 'describe' && t('policyTitle')}
              {screen === 'review' && t('policyReviewTitle')}
              {screen === 'saved' && t('policySavedTitle')}
            </h2>
          </div>
          <button
            className="profile-close"
            type="button"
            onClick={close}
            aria-label={t('policyClose')}
          >
            ×
          </button>
        </div>

        {screen === 'describe' && (
          <form className="policy-describe" onSubmit={extract}>
            <p className="profile-intro">{t('policyIntro')}</p>
            <section
              className="policy-preset-card"
              aria-labelledby="long-term-tech-value-title"
            >
              <div className="policy-preset-copy">
                <span className="policy-preset-status">{t('policyPresetStatus')}</span>
                <h3 id="long-term-tech-value-title">Long-Term Tech Value</h3>
                <p>{t('policyPresetDescription')}</p>
                <small>{t('policyPresetDefaults')}</small>
                <em>{t('policyPresetDisclaimer')}</em>
              </div>
              <button
                className="profile-secondary"
                type="button"
                disabled={extracting || loadingPreset}
                onClick={useLongTermTechValuePreset}
              >
                {loadingPreset ? t('policyPresetLoading') : t('policyPresetUse')}
              </button>
            </section>
            <div className="policy-input-divider">
              <span>{t('policyOrDescribe')}</span>
            </div>
            <label htmlFor="policy-preferences">
              <span>{t('policyInputLabel')}</span>
              <textarea
                id="policy-preferences"
                rows="9"
                maxLength="12000"
                value={preferences}
                placeholder={t('policyInputPlaceholder')}
                onChange={(event) => setPreferences(event.target.value)}
              />
            </label>
            {error && <p className="profile-error" role="alert">{error}</p>}
            <div className="profile-safety">
              <strong>{t('policyDraftBadge')}</strong>
              <span>{t('policyIntro')}</span>
            </div>
            <div className="profile-actions policy-actions">
              <span className="policy-input-count">{preferences.length} / 12,000</span>
              <button
                className="profile-primary"
                type="submit"
                disabled={extracting || loadingPreset || !preferences.trim()}
              >
                {extracting ? t('policyExtracting') : t('policyExtract')}
              </button>
            </div>
          </form>
        )}

        {screen === 'review' && policy && (
          <div className="policy-review">
            <div className="policy-review-intro">
              <p className="profile-intro">{t('policyReviewIntro')}</p>
              <span className="policy-draft-badge">
                {proposalSource === LONG_TERM_TECH_VALUE_PRESET_ID
                  ? t('policyPresetDraftBadge')
                  : t('policyDraftBadge')}
              </span>
            </div>
            {proposalSource === LONG_TERM_TECH_VALUE_PRESET_ID && (
              <aside className="policy-preset-notice">
                <strong>{t('policyPresetEditable')}</strong>
                <span>{t('policyPresetDisclaimer')}</span>
              </aside>
            )}
            <div className="policy-metadata">
              <label htmlFor="policy-name">
                <span>{t('policyName')}</span>
                <input
                  id="policy-name"
                  value={policy.name}
                  onChange={(event) => updateMetadata('name', event.target.value)}
                />
              </label>
              <label htmlFor="policy-description">
                <span>{t('policyDescription')}</span>
                <textarea
                  id="policy-description"
                  rows="2"
                  value={policy.description || ''}
                  onChange={(event) => updateMetadata('description', event.target.value)}
                />
              </label>
            </div>

            {proposalSource === 'ai' && (
              <p className="policy-languages">
                <strong>{t('policyDetectedLanguages')}:</strong>{' '}
                {proposal.detected_languages.join(' + ')}
              </p>
            )}

            {proposal.issues.length > 0 && (
              <section className="policy-issues" aria-labelledby="policy-issues-title">
                <h3 id="policy-issues-title">{t('policyIssues')}</h3>
                {proposal.issues.map((issue) => (
                  <label key={issue.issue_id}>
                    <input
                      type="checkbox"
                      checked={Boolean(acknowledged[issue.issue_id])}
                      onChange={(event) => setAcknowledged((current) => ({
                        ...current,
                        [issue.issue_id]: event.target.checked,
                      }))}
                    />
                    <span>
                      <strong>{issue.severity}</strong>
                      {issue.message}
                      {issue.source_text && <small>“{issue.source_text}”</small>}
                      <em>{t('policyAcknowledge')}</em>
                    </span>
                  </label>
                ))}
              </section>
            )}

            <div className="policy-groups">
              {RULE_GROUPS.map(([family, titleKey]) => {
                const rules = policy.initial_version[family]
                return (
                  <section className="policy-group" key={family}>
                    <header>
                      <h3>{t(titleKey)}</h3>
                      <span>{rules.length}</span>
                    </header>
                    {rules.length === 0 && (
                      <p className="policy-empty">{t('policyNoRules')}</p>
                    )}
                    {rules.map((rule, index) => (
                      <RuleEditor
                        family={family}
                        index={index}
                        rule={rule}
                        key={`${family}-${index}`}
                        onChange={(field, value) => updateRule(family, index, field, value)}
                        onRemove={() => removeRule(family, index)}
                      />
                    ))}
                    <button
                      className="policy-add"
                      type="button"
                      onClick={() => addRule(family)}
                    >
                      + {t('policyAddRule')}
                    </button>
                  </section>
                )
              })}
            </div>

            <div className="policy-confirmation">
              <label>
                <input
                  type="checkbox"
                  checked={makeDefault}
                  onChange={(event) => setMakeDefault(event.target.checked)}
                />
                <span>{t('policyMakeDefault')}</span>
              </label>
              {proposalSource === LONG_TERM_TECH_VALUE_PRESET_ID && (
                <p className="policy-default-scope">{t('policyPresetDefaultScope')}</p>
              )}
              <label className="policy-explicit-confirm">
                <input
                  type="checkbox"
                  checked={explicitConfirmation}
                  onChange={(event) => setExplicitConfirmation(event.target.checked)}
                />
                <span>{t('policyExplicitConfirm')}</span>
              </label>
            </div>
            {error && <p className="profile-error" role="alert">{error}</p>}
            <div className="profile-actions">
              <button
                type="button"
                className="profile-secondary"
                onClick={() => setScreen('describe')}
              >
                {t('policyBack')}
              </button>
              <button
                type="button"
                className="profile-primary"
                disabled={saving || !explicitConfirmation || !allIssuesAcknowledged}
                onClick={confirm}
              >
                {saving ? t('policySaving') : t('policyConfirm')}
              </button>
            </div>
          </div>
        )}

        {screen === 'saved' && savedPolicy && (
          <div className="policy-saved">
            <div className="policy-saved-mark" aria-hidden="true">✓</div>
            <p>
              <strong>{savedPolicy.name}</strong>
              {t('policySavedText')} {savedPolicy.published_version_number}.
            </p>
            <button className="profile-primary" type="button" onClick={close}>
              {t('policyDone')}
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
