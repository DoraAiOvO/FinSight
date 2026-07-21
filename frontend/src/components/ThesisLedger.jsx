import { useEffect, useState } from 'react'

import { useTranslation } from '../hooks/useTranslation.js'
import { api } from '../lib/api.js'
import {
  ASSUMPTION_STATUSES,
  assumptionDraft,
  assumptionReady,
  assumptionStatusKey,
  buildAssumptionPayload,
  conditionSummary,
  ledgerEvidence,
  replaceAssumption,
} from '../lib/thesisLedger.js'


function AssumptionFields({ draft, onChange, t }) {
  const setField = (field, value) => onChange({ ...draft, [field]: value })
  return (
    <div className="ledger-form-grid">
      <label className="ledger-form-wide">
        <span>{t('assumptionDescription')}</span>
        <textarea
          maxLength="2000"
          required
          value={draft.description}
          onChange={(event) => setField('description', event.target.value)}
          placeholder={t('assumptionDescriptionPlaceholder')}
        />
      </label>
      <label>
        <span>{t('conditionType')}</span>
        <select
          value={draft.condition_type}
          onChange={(event) => setField('condition_type', event.target.value)}
        >
          <option value="metric">{t('metricCondition')}</option>
          <option value="event">{t('eventCondition')}</option>
        </select>
      </label>
      <label>
        <span>{t('assumptionStatus')}</span>
        <select
          value={draft.current_status}
          onChange={(event) => setField('current_status', event.target.value)}
        >
          {ASSUMPTION_STATUSES.map((status) => (
            <option value={status} key={status}>{t(assumptionStatusKey(status))}</option>
          ))}
        </select>
      </label>
      {draft.condition_type === 'metric' ? (
        <>
          <label>
            <span>{t('metricKey')}</span>
            <input
              maxLength="120"
              required
              value={draft.metric_key}
              onChange={(event) => setField('metric_key', event.target.value)}
              placeholder={t('metricKeyPlaceholder')}
            />
          </label>
          <label>
            <span>{t('operator')}</span>
            <select
              value={draft.operator}
              onChange={(event) => setField('operator', event.target.value)}
            >
              {['>', '>=', '<', '<=', '==', '!='].map((operator) => (
                <option value={operator} key={operator}>{operator}</option>
              ))}
            </select>
          </label>
          <label className="ledger-form-wide">
            <span>{t('targetValue')}</span>
            <input
              maxLength="120"
              required
              value={draft.target_value}
              onChange={(event) => setField('target_value', event.target.value)}
              placeholder={t('targetValuePlaceholder')}
            />
          </label>
        </>
      ) : (
        <label className="ledger-form-wide">
          <span>{t('eventCondition')}</span>
          <textarea
            maxLength="2000"
            required
            value={draft.event_condition}
            onChange={(event) => setField('event_condition', event.target.value)}
            placeholder={t('eventConditionPlaceholder')}
          />
        </label>
      )}
    </div>
  )
}


function AssumptionEditor({ initial, busy, onSave, onCancel, t }) {
  const [draft, setDraft] = useState(() => assumptionDraft(initial))

  async function submit(event) {
    event.preventDefault()
    if (!assumptionReady(draft)) return
    await onSave(buildAssumptionPayload(draft))
  }

  return (
    <form className="ledger-editor" onSubmit={submit}>
      <AssumptionFields draft={draft} onChange={setDraft} t={t} />
      <div className="ledger-form-actions">
        <button type="button" onClick={onCancel}>{t('cancel')}</button>
        <button type="submit" disabled={busy || !assumptionReady(draft)}>
          {busy ? t('savingAssumption') : t('saveAssumption')}
        </button>
      </div>
    </form>
  )
}


function EvidenceEditor({ busy, onSave, onCancel, t }) {
  const [kind, setKind] = useState('supporting_evidence')
  const [claim, setClaim] = useState('')
  const [source, setSource] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [confidence, setConfidence] = useState('0.7')

  async function submit(event) {
    event.preventDefault()
    if (!claim.trim() || !source.trim()) return
    await onSave(kind, ledgerEvidence({
      claim,
      source,
      source_url: sourceUrl,
      confidence,
    }))
  }

  return (
    <form className="ledger-evidence-form" onSubmit={submit}>
      <label>
        <span>{t('evidenceType')}</span>
        <select value={kind} onChange={(event) => setKind(event.target.value)}>
          <option value="supporting_evidence">{t('supportingEvidence')}</option>
          <option value="contradicting_evidence">{t('contradictingEvidence')}</option>
        </select>
      </label>
      <label className="ledger-form-wide">
        <span>{t('evidenceClaim')}</span>
        <textarea
          required
          maxLength="2000"
          value={claim}
          onChange={(event) => setClaim(event.target.value)}
          placeholder={t('evidenceClaimPlaceholder')}
        />
      </label>
      <label>
        <span>{t('evidenceSource')}</span>
        <input
          required
          maxLength="300"
          value={source}
          onChange={(event) => setSource(event.target.value)}
          placeholder={t('evidenceSourcePlaceholder')}
        />
      </label>
      <label>
        <span>{t('evidenceConfidence')}</span>
        <select value={confidence} onChange={(event) => setConfidence(event.target.value)}>
          <option value="0.4">{t('confidenceLow')}</option>
          <option value="0.7">{t('confidenceMedium')}</option>
          <option value="0.9">{t('confidenceHigh')}</option>
        </select>
      </label>
      <label className="ledger-form-wide">
        <span>{t('evidenceUrl')}</span>
        <input
          type="url"
          maxLength="2000"
          value={sourceUrl}
          onChange={(event) => setSourceUrl(event.target.value)}
          placeholder="https://"
        />
      </label>
      <div className="ledger-form-actions ledger-form-wide">
        <button type="button" onClick={onCancel}>{t('cancel')}</button>
        <button type="submit" disabled={busy || !claim.trim() || !source.trim()}>
          {busy ? t('savingEvidence') : t('addEvidence')}
        </button>
      </div>
    </form>
  )
}


function EvidenceList({ items, emptyText }) {
  if (!items.length) return <p className="ledger-evidence-empty">{emptyText}</p>
  return (
    <ul className="ledger-evidence-list">
      {items.map((item) => (
        <li key={`${item.recorded_at}:${item.claim}`}>
          <strong>{item.claim}</strong>
          <span>{item.source} · {item.as_of_date}</span>
          {item.source_url && (
            <a href={item.source_url} target="_blank" rel="noreferrer">↗</a>
          )}
        </li>
      ))}
    </ul>
  )
}


function HistoryText({ entry, t }) {
  if (entry.change_type === 'created') return t('historyCreated')
  if (entry.change_type === 'status_changed') {
    const previous = entry.previous_values?.current_status
    const current = entry.current_values?.current_status
    return `${t(assumptionStatusKey(previous))} → ${t(assumptionStatusKey(current))}`
  }
  return t('historyUpdated')
}


function AssumptionCard({
  assumption,
  busy,
  locale,
  onUpdate,
  onRemove,
  t,
}) {
  const [editing, setEditing] = useState(false)
  const [addingEvidence, setAddingEvidence] = useState(false)

  async function updateStatus(event) {
    await onUpdate({
      current_status: event.target.value,
      change_reason: t('manualStatusReason'),
    })
  }

  async function saveEdit(payload) {
    const updated = await onUpdate({
      ...payload,
      change_reason: t('manualAssumptionEditReason'),
    })
    if (updated) setEditing(false)
  }

  async function saveEvidence(kind, evidence) {
    const updated = await onUpdate({
      [kind]: [...assumption[kind], evidence],
      change_reason: t('manualEvidenceReason'),
    })
    if (updated) setAddingEvidence(false)
  }

  function confirmRemove() {
    if (window.confirm(t('deleteAssumptionConfirm'))) onRemove()
  }

  return (
    <article className="ledger-assumption">
      <header>
        <div>
          <span className={`ledger-status ${assumption.current_status}`}>
            {t(assumptionStatusKey(assumption.current_status))}
          </span>
          <strong>{assumption.description}</strong>
          <code>{conditionSummary(assumption)}</code>
        </div>
        <label>
          <span>{t('assumptionStatus')}</span>
          <select value={assumption.current_status} disabled={busy} onChange={updateStatus}>
            {ASSUMPTION_STATUSES.map((status) => (
              <option value={status} key={status}>{t(assumptionStatusKey(status))}</option>
            ))}
          </select>
        </label>
      </header>

      <div className="ledger-evidence-grid">
        <section>
          <h5>{t('supportingEvidence')} <span>{assumption.supporting_evidence.length}</span></h5>
          <EvidenceList items={assumption.supporting_evidence} emptyText={t('noSupportingEvidence')} />
        </section>
        <section>
          <h5>{t('contradictingEvidence')} <span>{assumption.contradicting_evidence.length}</span></h5>
          <EvidenceList items={assumption.contradicting_evidence} emptyText={t('noContradictingEvidence')} />
        </section>
      </div>

      {editing && (
        <AssumptionEditor
          key={assumption.updated_at}
          initial={assumption}
          busy={busy}
          onSave={saveEdit}
          onCancel={() => setEditing(false)}
          t={t}
        />
      )}
      {addingEvidence && (
        <EvidenceEditor
          busy={busy}
          onSave={saveEvidence}
          onCancel={() => setAddingEvidence(false)}
          t={t}
        />
      )}

      <footer className="ledger-assumption-actions">
        <button type="button" disabled={busy} onClick={() => setEditing((value) => !value)}>
          {t('editAssumption')}
        </button>
        <button type="button" disabled={busy} onClick={() => setAddingEvidence((value) => !value)}>
          {t('addEvidence')}
        </button>
        <button className="danger" type="button" disabled={busy} onClick={confirmRemove}>
          {t('deleteAssumption')}
        </button>
      </footer>

      <details className="ledger-history">
        <summary>{t('changeHistory')} · {assumption.history.length}</summary>
        <ol>
          {assumption.history.map((entry) => (
            <li key={entry.id}>
              <span />
              <div>
                <strong><HistoryText entry={entry} t={t} /></strong>
                {entry.reason && <p>{entry.reason}</p>}
                <time>{new Date(entry.changed_at).toLocaleString(locale, {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}</time>
              </div>
            </li>
          ))}
        </ol>
      </details>
    </article>
  )
}


export default function ThesisLedger({ customerId, ticker, onChanged }) {
  const { t, locale } = useTranslation()
  const [theses, setTheses] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [creating, setCreating] = useState(false)
  const [addingToThesis, setAddingToThesis] = useState(null)
  const [title, setTitle] = useState('')
  const [statement, setStatement] = useState('')
  const [confidence, setConfidence] = useState('60')
  const [firstAssumption, setFirstAssumption] = useState(assumptionDraft)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    api.theses.list(customerId, ticker, 'active')
      .then((items) => { if (active) setTheses(items) })
      .catch((requestError) => { if (active) setError(requestError.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [customerId, ticker])

  function changed(message) {
    setNotice(message)
    onChanged?.()
  }

  async function createThesis(event) {
    event.preventDefault()
    if (!title.trim() || !statement.trim() || !assumptionReady(firstAssumption)) return
    setBusy('create-thesis')
    setError(null)
    setNotice(null)
    try {
      const created = await api.theses.create(customerId, {
        ticker,
        title: title.trim(),
        statement: statement.trim(),
        confidence: Number(confidence) / 100,
        assumptions: [buildAssumptionPayload(firstAssumption)],
      })
      setTheses((current) => [created, ...current])
      setTitle('')
      setStatement('')
      setConfidence('60')
      setFirstAssumption(assumptionDraft())
      setCreating(false)
      changed(t('thesisCreated'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(null)
    }
  }

  async function addAssumption(thesisId, payload) {
    setBusy(`add:${thesisId}`)
    setError(null)
    try {
      const created = await api.theses.assumptions.create(customerId, thesisId, payload)
      setTheses((current) => current.map((thesis) => (
        thesis.id === thesisId
          ? { ...thesis, assumptions: [...thesis.assumptions, created] }
          : thesis
      )))
      setAddingToThesis(null)
      changed(t('assumptionCreated'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(null)
    }
  }

  async function updateAssumption(thesisId, assumptionId, payload) {
    setBusy(`assumption:${assumptionId}`)
    setError(null)
    try {
      const updated = await api.theses.assumptions.update(
        customerId, thesisId, assumptionId, payload,
      )
      setTheses((current) => replaceAssumption(current, thesisId, updated))
      changed(t('assumptionUpdated'))
      return updated
    } catch (requestError) {
      setError(requestError.message)
      return null
    } finally {
      setBusy(null)
    }
  }

  async function removeAssumption(thesisId, assumptionId) {
    setBusy(`assumption:${assumptionId}`)
    setError(null)
    try {
      await api.theses.assumptions.remove(customerId, thesisId, assumptionId)
      setTheses((current) => current.map((thesis) => (
        thesis.id === thesisId
          ? {
              ...thesis,
              assumptions: thesis.assumptions.filter((item) => item.id !== assumptionId),
            }
          : thesis
      )))
      changed(t('assumptionDeleted'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="thesis-ledger">
      <div className="ledger-heading">
        <div>
          <p className="section-kicker">{t('thesisLedgerKicker')}</p>
          <h3>{t('thesisLedgerTitle')}</h3>
          <p>{t('thesisLedgerDescription')}</p>
        </div>
        <button type="button" onClick={() => setCreating((value) => !value)}>
          {creating ? t('cancel') : t('newThesis')}
        </button>
      </div>

      {(error || notice) && (
        <p className={error ? 'ledger-message error' : 'ledger-message'} role="status">
          {error || notice}
        </p>
      )}

      {creating && (
        <form className="ledger-create" onSubmit={createThesis}>
          <div className="ledger-form-grid">
            <label>
              <span>{t('thesisTitle')}</span>
              <input
                required
                maxLength="200"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t('thesisTitlePlaceholder')}
              />
            </label>
            <label>
              <span>{t('thesisConfidence')} · {confidence}%</span>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={confidence}
                onChange={(event) => setConfidence(event.target.value)}
              />
            </label>
            <label className="ledger-form-wide">
              <span>{t('thesisStatement')}</span>
              <textarea
                required
                maxLength="5000"
                value={statement}
                onChange={(event) => setStatement(event.target.value)}
                placeholder={t('thesisStatementPlaceholder')}
              />
            </label>
          </div>
          <div className="ledger-initial-assumption">
            <h4>{t('firstMeasurableAssumption')}</h4>
            <AssumptionFields draft={firstAssumption} onChange={setFirstAssumption} t={t} />
          </div>
          <div className="ledger-form-actions">
            <button type="button" onClick={() => setCreating(false)}>{t('cancel')}</button>
            <button
              type="submit"
              disabled={busy === 'create-thesis' || !title.trim()
                || !statement.trim() || !assumptionReady(firstAssumption)}
            >
              {busy === 'create-thesis' ? t('savingThesis') : t('createThesis')}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="ledger-empty">{t('loadingTheses')}</p>
      ) : theses.length === 0 ? (
        <div className="ledger-empty">
          <strong>{t('noTheses')}</strong>
          <span>{t('noThesesExplanation')}</span>
        </div>
      ) : (
        <div className="ledger-list">
          {theses.map((thesis) => (
            <article className="ledger-thesis" key={thesis.id}>
              <header className="ledger-thesis-heading">
                <div>
                  <span>{thesis.ticker} · {Math.round((thesis.confidence || 0) * 100)}% {t('confidence')}</span>
                  <h4>{thesis.title}</h4>
                  <p>{thesis.statement}</p>
                </div>
                <button type="button" onClick={() => setAddingToThesis(
                  addingToThesis === thesis.id ? null : thesis.id,
                )}>
                  {t('addAssumption')}
                </button>
              </header>

              {addingToThesis === thesis.id && (
                <AssumptionEditor
                  busy={busy === `add:${thesis.id}`}
                  onSave={(payload) => addAssumption(thesis.id, payload)}
                  onCancel={() => setAddingToThesis(null)}
                  t={t}
                />
              )}

              <div className="ledger-assumption-list">
                {thesis.assumptions.length === 0 ? (
                  <p className="ledger-evidence-empty">{t('noAssumptions')}</p>
                ) : thesis.assumptions.map((assumption) => (
                  <AssumptionCard
                    key={assumption.id}
                    assumption={assumption}
                    busy={busy === `assumption:${assumption.id}`}
                    locale={locale}
                    onUpdate={(payload) => updateAssumption(
                      thesis.id, assumption.id, payload,
                    )}
                    onRemove={() => removeAssumption(thesis.id, assumption.id)}
                    t={t}
                  />
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
