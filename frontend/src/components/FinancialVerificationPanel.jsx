import { useMemo, useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'

function metricLabel(key) {
  return key
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function periodLabel(metric) {
  if (metric.fiscal_year && metric.fiscal_quarter) {
    return `FY${metric.fiscal_year} Q${metric.fiscal_quarter}`
  }
  if (metric.fiscal_year) return `FY${metric.fiscal_year}`
  return `${metric.period_type} · ${metric.period_end}`
}

function metricValue(metric, locale) {
  const formatted = Number(metric.value).toLocaleString(locale, {
    maximumFractionDigits: metric.unit === 'ratio' ? 4 : 2,
  })
  if (metric.currency) return `${formatted} ${metric.currency}`
  if (metric.unit === 'percent') return `${formatted}%`
  return formatted
}

export default function FinancialVerificationPanel({ evidence }) {
  const { t, locale } = useTranslation()
  const [showAll, setShowAll] = useState(false)
  const metrics = useMemo(
    () => new Map((evidence?.metrics || []).map((metric) => [metric.metric_id, metric])),
    [evidence],
  )
  const rows = useMemo(() => {
    const selected = (evidence?.verification_results || [])
      .map((result) => ({ result, metric: metrics.get(result.selected_metric_id) }))
      .filter((item) => item.metric)
      .sort((left, right) => (
        right.metric.period_end.localeCompare(left.metric.period_end)
          || left.metric.metric_key.localeCompare(right.metric.metric_key)
      ))
    if (showAll) return selected
    const latest = new Map()
    selected.forEach((item) => {
      if (!latest.has(item.metric.metric_key)) latest.set(item.metric.metric_key, item)
    })
    return [...latest.values()]
  }, [evidence, metrics, showAll])

  if (!evidence) return null

  return (
    <section className="card verification-card" aria-labelledby="verification-title">
      <div className="section-heading verification-heading">
        <div>
          <p className="card-kicker">{t('verificationKicker')}</p>
          <h3 id="verification-title">{t('verificationTitle')}</h3>
          <p className="muted">{t('verificationIntro')}</p>
        </div>
        <button type="button" className="verification-toggle" onClick={() => setShowAll(!showAll)}>
          {showAll ? t('verificationLatest') : t('verificationAllPeriods')}
        </button>
      </div>

      <div className="verification-table-wrap">
        <table className="verification-table">
          <thead>
            <tr>
              <th>{t('verificationMetric')}</th>
              <th>{t('verificationSource')}</th>
              <th>{t('verificationPeriod')}</th>
              <th>{t('verificationAsOf')}</th>
              <th>{t('verificationStatus')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ result, metric }) => (
              <tr key={result.verification_result_id}>
                <td>
                  <strong>{metricLabel(metric.metric_key)}</strong>
                  <span>{metricValue(metric, locale)}</span>
                  {metric.calculation_formula && (
                    <small>{t('verificationFormula')}: <code>{metric.calculation_formula}</code></small>
                  )}
                </td>
                <td>
                  {/^https?:\/\//.test(metric.source_document) ? (
                    <a href={metric.source_document} target="_blank" rel="noreferrer">
                      {metric.provider} ↗
                    </a>
                  ) : <strong>{metric.provider}</strong>}
                  <small>{metric.source_concept}</small>
                </td>
                <td>{periodLabel(metric)}</td>
                <td>
                  {metric.period_end}
                  <small>{metric.filing_date ? `${t('verificationFiled')} ${metric.filing_date}` : t('verificationNoFilingDate')}</small>
                </td>
                <td>
                  <span className={`verification-status status-${result.verification_status.toLowerCase()}`}>
                    {result.verification_status}
                  </span>
                  <small>{result.explanation}</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {evidence.conflicts.length > 0 && (
        <div className="source-conflicts" role="alert">
          <h4>{t('verificationConflicts')}</h4>
          {evidence.conflicts.map((conflict) => (
            <article key={conflict.conflict_id}>
              <strong>{metricLabel(conflict.metric_key)} · {conflict.financial_period_id}</strong>
              <p>{conflict.providers.map((provider, index) => (
                `${provider}: ${Number(conflict.values[index]).toLocaleString(locale)}`
              )).join(' · ')}</p>
              <small>
                {t('verificationConflictDifference')} {(conflict.relative_difference * 100).toLocaleString(locale, { maximumFractionDigits: 2 })}% · {t(
                  conflict.resolution === 'UNRESOLVED_NO_PRIMARY'
                    ? 'verificationUnresolvedNoPrimary'
                    : 'verificationUnresolved'
                )}
              </small>
            </article>
          ))}
        </div>
      )}

      {(evidence.missing_metric_keys.length > 0 || evidence.validation_failures.length > 0) && (
        <details className="verification-limitations">
          <summary>{t('verificationLimitations')}</summary>
          {evidence.missing_metric_keys.length > 0 && (
            <p>{t('verificationMissing')}: {evidence.missing_metric_keys.map(metricLabel).join(', ')}</p>
          )}
          {evidence.validation_failures.map((failure) => <p key={failure}>{failure}</p>)}
        </details>
      )}
    </section>
  )
}
