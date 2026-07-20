import { useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'
import { displayDataPoint, evidenceText } from '../lib/api.js'

const SEVERITY_KEYS = { high: 'sevHigh', medium: 'sevMedium', low: 'sevLow' }

function EvidenceList({ items, professional }) {
  const { t, ts, tb } = useTranslation()
  return (
    <div className="evidence-list">
      {items.map((item, index) => {
        const confidence = `${Math.round((item.value.confidence || 0) * 100)}%`
        const provenance = t('evidenceProvenance')
          .replace('{provider}', item.value.provider || '—')
          .replace('{date}', item.value.as_of_date || '—')
          .replace('{confidence}', confidence)
        return (
          <div className="evidence-row" key={`${item.metric}-${index}`}>
            <span><small>{ts(item.metric)}</small><strong>{displayDataPoint(item.value)}</strong></span>
            <div>
              <p>{tb(item.benchmark_key, item.benchmark_params, evidenceText(item.benchmark))}</p>
              {professional && <small className="evidence-provenance">{provenance}</small>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function InsightCard({ insight, defaultOpen = false, explanationDepth = 'standard' }) {
  const { t, ts } = useTranslation()
  const [open, setOpen] = useState(defaultOpen)
  const isRisk = insight.kind === 'risk'
  const title = evidenceText(insight.title)
  const explanation = evidenceText(insight.explanation)

  return (
    <article className={`insight ${insight.kind}${insight.highlighted ? ' profile-highlighted-insight' : ''}`}>
      <button className="insight-head" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="insight-signal" aria-hidden="true" />
        <span className="insight-title-wrap">
          <span className="insight-kind">{isRisk ? t('riskSignal') : t('opportunitySignal')}</span>
          <span className="insight-title">{ts(title)}</span>
          {insight.highlighted && <span className="insight-profile-label">{t('highlightedForProfile')}</span>}
        </span>
        <span className={`severity severity-${insight.severity}`}>
          {t(SEVERITY_KEYS[insight.severity] || insight.severity)}
        </span>
        <span className="caret" aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="insight-body">
          <p>{ts(explanation)}</p>
          {explanationDepth === 'simple' ? (
            <details className="simple-evidence">
              <summary>{t('supportingEvidence')}</summary>
              <EvidenceList items={insight.evidence} professional={false} />
            </details>
          ) : (
            <EvidenceList
              items={insight.evidence}
              professional={explanationDepth === 'professional'}
            />
          )}
        </div>
      )}
    </article>
  )
}

export default function AnalysisPanel({ analysis, presentation = analysis.presentation }) {
  const { t } = useTranslation()
  const [filter, setFilter] = useState('all')
  const risks = analysis.insights.filter((insight) => insight.kind === 'risk')
  const opportunities = analysis.insights.filter((insight) => insight.kind === 'opportunity')
  const visible = filter === 'all'
    ? analysis.insights
    : analysis.insights.filter((insight) => insight.kind === filter)
  const explanationDepth = presentation?.explanation_depth || 'standard'
  const reportDepth = presentation?.report_depth || 'standard'
  const firstHighlightedIndex = visible.findIndex((insight) => insight.highlighted)

  function defaultOpen(insight, index) {
    if (reportDepth === 'quick') {
      return firstHighlightedIndex >= 0 ? index === firstHighlightedIndex : index === 0
    }
    if (reportDepth === 'deep') return insight.highlighted || index < 2
    return index === 0
  }

  return (
    <section className="card analysis-card">
      <div className="section-heading">
        <div>
          <p className="card-kicker">{t('analysisKicker')}</p>
          <h3>{t('analysisTitle')}</h3>
        </div>
        <div className="balance-counts" aria-label={`${opportunities.length} ${t('upside')} · ${risks.length} ${t('riskCount')}`}>
          <span className="opportunity-count">{opportunities.length} {t('upside')}</span>
          <span className="risk-count">{risks.length} {t('riskCount')}</span>
        </div>
      </div>

      {analysis.ai_narrative && (
        <div className="ai-note">
          <span className="ai-label">{t('synthesis')}</span>
          {presentation?.personalized && (
            <span className="explanation-depth-label">
              {t({
                simple: 'explanationSimple',
                standard: 'explanationStandard',
                professional: 'explanationProfessional',
              }[explanationDepth])}
            </span>
          )}
          <p>{evidenceText(analysis.ai_narrative)}</p>
        </div>
      )}

      {analysis.insights.length > 0 && (
        <div className="insight-filters" aria-label={t('filterAria')}>
          {[
            ['all', t('filterAll')],
            ['opportunity', t('filterOpportunities')],
            ['risk', t('filterRisks')],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={filter === value ? 'active' : ''}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {analysis.insights.length === 0 && (
        <p className="empty-copy">{t('noFlags')}</p>
      )}
      <div className="insight-list">
        {visible.map((insight, index) => (
          <InsightCard
            key={`${insight.kind}-${insight.code || insight.title}`}
            insight={insight}
            defaultOpen={defaultOpen(insight, index)}
            explanationDepth={explanationDepth}
          />
        ))}
      </div>
      <p className="disclaimer">{t('disclaimer')}</p>
    </section>
  )
}
