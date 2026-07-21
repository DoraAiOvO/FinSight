export const ASSUMPTION_STATUSES = [
  'unreviewed',
  'monitoring',
  'supported',
  'challenged',
  'invalidated',
]

export function blankAssumption() {
  return {
    description: '',
    condition_type: 'metric',
    metric_key: '',
    operator: '>=',
    target_value: '',
    event_condition: '',
    current_status: 'unreviewed',
    supporting_evidence: [],
    contradicting_evidence: [],
  }
}

export function assumptionDraft(assumption = null) {
  return assumption ? {
    ...blankAssumption(),
    ...assumption,
  } : blankAssumption()
}

export function assumptionReady(draft) {
  if (!draft.description.trim()) return false
  if (draft.condition_type === 'event') return Boolean(draft.event_condition.trim())
  return Boolean(draft.metric_key.trim() && draft.operator && draft.target_value.trim())
}

export function buildAssumptionPayload(draft) {
  const payload = {
    description: draft.description.trim(),
    condition_type: draft.condition_type,
    current_status: draft.current_status,
    supporting_evidence: draft.supporting_evidence || [],
    contradicting_evidence: draft.contradicting_evidence || [],
  }
  if (draft.condition_type === 'event') {
    return {
      ...payload,
      metric_key: null,
      operator: null,
      target_value: null,
      event_condition: draft.event_condition.trim(),
    }
  }
  return {
    ...payload,
    metric_key: draft.metric_key.trim(),
    operator: draft.operator,
    target_value: draft.target_value.trim(),
    event_condition: null,
  }
}

export function ledgerEvidence(values, now = new Date()) {
  const timestamp = now.toISOString()
  return {
    claim: values.claim.trim(),
    source: values.source.trim(),
    source_url: values.source_url?.trim() || null,
    as_of_date: timestamp.slice(0, 10),
    recorded_at: timestamp,
    confidence: Number(values.confidence),
  }
}

export function conditionSummary(assumption) {
  if (assumption.condition_type === 'event') return assumption.event_condition || ''
  return [assumption.metric_key, assumption.operator, assumption.target_value]
    .filter(Boolean)
    .join(' ')
}

export function assumptionStatusKey(status) {
  return {
    unreviewed: 'assumptionUnreviewed',
    monitoring: 'assumptionMonitoring',
    supported: 'assumptionSupported',
    challenged: 'assumptionChallenged',
    invalidated: 'assumptionInvalidated',
  }[status] || 'assumptionUnreviewed'
}

export function replaceAssumption(theses, thesisId, updatedAssumption) {
  return theses.map((thesis) => (
    thesis.id === thesisId
      ? {
          ...thesis,
          assumptions: thesis.assumptions.map((assumption) => (
            assumption.id === updatedAssumption.id ? updatedAssumption : assumption
          )),
        }
      : thesis
  ))
}
