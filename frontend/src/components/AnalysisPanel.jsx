import { useState } from 'react'

function InsightCard({ insight, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const isRisk = insight.kind === 'risk'

  return (
    <article className={`insight ${insight.kind}`}>
      <button className="insight-head" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="insight-signal" aria-hidden="true" />
        <span className="insight-title-wrap">
          <span className="insight-kind">{isRisk ? 'Risk signal' : 'Opportunity signal'}</span>
          <span className="insight-title">{insight.title}</span>
        </span>
        <span className={`severity severity-${insight.severity}`}>{insight.severity}</span>
        <span className="caret" aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="insight-body">
          <p>{insight.explanation}</p>
          <div className="evidence-list">
            {insight.evidence.map((item, index) => (
              <div className="evidence-row" key={`${item.metric}-${index}`}>
                <span><small>{item.metric}</small><strong>{item.value}</strong></span>
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
          <p className="card-kicker">Transparent rules engine</p>
          <h3>Risks &amp; opportunities</h3>
        </div>
        <div className="balance-counts" aria-label={`${opportunities.length} opportunities and ${risks.length} risks`}>
          <span className="opportunity-count">{opportunities.length} upside</span>
          <span className="risk-count">{risks.length} risk</span>
        </div>
      </div>

      {analysis.ai_narrative && (
        <div className="ai-note">
          <span className="ai-label">FinSight synthesis</span>
          <p>{analysis.ai_narrative}</p>
        </div>
      )}

      {analysis.insights.length > 0 && (
        <div className="insight-filters" aria-label="Filter research signals">
          {[
            ['all', 'All evidence'],
            ['opportunity', 'Opportunities'],
            ['risk', 'Risks'],
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
        <p className="empty-copy">No notable flags were triggered by the available metrics.</p>
      )}
      <div className="insight-list">
        {visible.map((insight, index) => (
          <InsightCard key={`${insight.kind}-${insight.title}`} insight={insight} defaultOpen={index === 0} />
        ))}
      </div>
      <p className="disclaimer">{analysis.disclaimer}</p>
    </section>
  )
}
