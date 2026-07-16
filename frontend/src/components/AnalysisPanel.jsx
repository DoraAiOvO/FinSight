import { useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'

const SEVERITY_KEYS = { high: 'sevHigh', medium: 'sevMedium', low: 'sevLow' }

function InsightCard({ insight, defaultOpen = false }) {
  const { t, ts } = useTranslation()
  const [open, setOpen] = useState(defaultOpen)
  const isRisk = insight.kind === 'risk'

  return (
    <article className={`insight ${insight.kind}`}>
      <button className="insight-head" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="insight-signal" aria-hidden="true" />
        <span className="insight-title-wrap">
          <span className="insight-kind">{isRisk ? t('riskSignal') : t('opportunitySignal')}</span>
          <span className="insight-title">{ts(insight.title)}</span>
        </span>
        <span className={`severity severity-${insight.severity}`}>
          {t(SEVERITY_KEYS[insight.severity] || insight.severity)}
        </span>
        <span className="caret" aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="insight-body">
          <p>{ts(insight.explanation)}</p>
          <div className="evidence-list">
            {insight.evidence.map((item, index) => (
              <div className="evidence-row" key={`${item.metric}-${index}`}>
                <span><small>{ts(item.metric)}</small><strong>{item.value}</strong></span>
                <p>{item.benchmark}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </article>
  )
}

export default function AnalysisPanel({ analysis }) {
  const { t } = useTranslation()
  const [filter, setFilter] = useState('all')
  const risks = analysis.insights.filter((insight) => insight.kind === 'risk')
  const opportunities = analysis.insights.filter((insight) => insight.kind === 'opportunity')
  const visible = filter === 'all'
    ? analysis.insights
    : analysis.insights.filter((insight) => insight.kind === filter)

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
          <p>{analysis.ai_narrative}</p>
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
          <InsightCard key={`${insight.kind}-${insight.title}`} insight={insight} defaultOpen={index === 0} />
        ))}
      </div>
      <p className="disclaimer">{t('disclaimer')}</p>
    </section>
  )
}
