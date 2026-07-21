import { useTranslation } from '../hooks/useTranslation.js'
import { evidenceText } from '../lib/api.js'
import {
  BENCHMARK_SCOPES,
  fillTemplate,
  formatBenchmarkValue,
  referenceFor,
} from '../lib/benchmarks.js'

const SCOPE_KEYS = {
  industry: 'benchmarkScopeIndustry',
  sector: 'benchmarkScopeSector',
  peers: 'benchmarkScopePeers',
  historical: 'benchmarkScopeHistorical',
}

function ReferenceValue({ metric, reference }) {
  const { t, locale } = useTranslation()
  if (!reference) return <span className="benchmark-missing">{t('benchmarkUnavailable')}</span>
  const rangeLabel = reference.range_kind === 'observed_range'
    ? t('benchmarkObservedRange')
    : t('benchmarkMiddleRange')
  return (
    <span className="benchmark-reference-value">
      <strong>{formatBenchmarkValue(metric.metric_key, reference.median, locale)}</strong>
      <small>
        {rangeLabel}{' '}
        {formatBenchmarkValue(metric.metric_key, reference.lower_bound, locale)}–
        {formatBenchmarkValue(metric.metric_key, reference.upper_bound, locale)}
      </small>
      <small>{fillTemplate(t('benchmarkSample'), { sampleSize: reference.sample_size })}</small>
    </span>
  )
}

export default function BenchmarkPanel({ benchmarks }) {
  const { t, ts, locale } = useTranslation()
  if (!benchmarks) return null

  return (
    <section className="card benchmark-card">
      <div className="section-heading benchmark-heading">
        <div>
          <p className="card-kicker">{t('benchmarkKicker')}</p>
          <h3>{t('benchmarkTitle')}</h3>
        </div>
        <div className="benchmark-classifications">
          {benchmarks.industry && <span>{t('benchmarkScopeIndustry')}: {benchmarks.industry}</span>}
          {benchmarks.sector && <span>{t('benchmarkScopeSector')}: {benchmarks.sector}</span>}
        </div>
      </div>

      <p className="benchmark-intro">{t('benchmarkIntro')}</p>

      {benchmarks.selected_peers?.length > 0 && (
        <div className="benchmark-peers">
          <strong>{t('benchmarkSelectedPeers')}</strong>
          <div>
            {benchmarks.selected_peers.map((peer) => (
              <article key={peer.ticker}>
                <span className="ticker-chip">{peer.ticker}</span>
                <div>
                  <strong>{peer.name || peer.ticker}</strong>
                  <small>{peer.industry || peer.sector || '—'}</small>
                  <p>{fillTemplate(
                    t(peer.selection_reason_key),
                    peer.selection_reason_params,
                  ) || evidenceText(peer.selection_reason)}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}

      {benchmarks.metrics?.length > 0 ? (
        <div className="benchmark-table-wrap">
          <table className="benchmark-table">
            <thead>
              <tr>
                <th>{t('benchmarkMetric')}</th>
                <th>{t('benchmarkCompany')}</th>
                {BENCHMARK_SCOPES.map((scope) => <th key={scope}>{t(SCOPE_KEYS[scope])}</th>)}
                <th>{t('benchmarkPrimary')}</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.metrics.map((metric) => {
                const primary = referenceFor(metric, metric.primary_scope)
                return (
                  <tr key={metric.metric_key}>
                    <th>{ts(metric.label)}</th>
                    <td className="benchmark-company-value">
                      {formatBenchmarkValue(metric.metric_key, metric.company_value, locale)}
                    </td>
                    {BENCHMARK_SCOPES.map((scope) => (
                      <td className={metric.primary_scope === scope ? 'primary' : ''} key={scope}>
                        <ReferenceValue metric={metric} reference={referenceFor(metric, scope)} />
                      </td>
                    ))}
                    <td className="benchmark-primary-reason">
                      {primary ? (
                        <>
                          <span>{t(SCOPE_KEYS[primary.scope])}</span>
                          <small>{fillTemplate(
                            t(primary.rationale_key),
                            primary.rationale_params,
                          )}</small>
                        </>
                      ) : <span className="benchmark-missing">{t('benchmarkUnavailable')}</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : <p className="empty-copy">{t('benchmarkNoMetrics')}</p>}

      <details className="benchmark-methodology">
        <summary>{t('benchmarkMethodology')}</summary>
        <p>{t('benchmarkMethodologyText')}</p>
        {benchmarks.limitations?.length > 0 && (
          <ul>
            {benchmarks.limitations.map((item, index) => (
              <li key={`${evidenceText(item)}-${index}`}>{ts(evidenceText(item))}</li>
            ))}
          </ul>
        )}
      </details>
    </section>
  )
}
