import { useState } from 'react'

function InsightCard({ insight }) {
  const [open, setOpen] = useState(false)
  const isRisk = insight.kind === 'risk'
  return (
    <div className={`insight ${insight.kind} sev-${insight.severity}`}>
      <button className="insight-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="insight-kind">{isRisk ? '⚠ Risk' : '↗ Opportunity'}</span>
        <span className="insight-title">{insight.title}</span>
        <span className={`sev-chip sev-${insight.severity}`}>{insight.severity}</span>
        <span className="caret">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="insight-body">
          <p>{insight.explanation}</p>
          <table className="evidence">
            <thead>
              <tr><th>Evidence</th><th>Value</th><th>Context</th></tr>
            </thead>
            <tbody>
              {insight.evidence.map((e, i) => (
                <tr key={i}>
                  <td>{e.metric}</td>
                  <td className="mono">{e.value}</td>
                  <td className="muted">{e.benchmark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function AnalysisPanel({ analysis }) {
  const risks = analysis.insights.filter((i) => i.kind === 'risk')
  const opps = analysis.insights.filter((i) => i.kind === 'opportunity')
  return (
    <section className="card">
      <h3>Risks &amp; opportunities <span className="muted">({risks.length} / {opps.length})</span></h3>
      {analysis.ai_narrative && <p className="ai-note">{analysis.ai_narrative}</p>}
      {analysis.insights.length === 0 && (
        <p className="muted">No notable flags from the available data — that itself is worth knowing.</p>
      )}
      {analysis.insights.map((ins, i) => (
        <InsightCard key={i} insight={ins} />
      ))}
      <p className="disclaimer">{analysis.disclaimer}</p>
    </section>
  )
}
