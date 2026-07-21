import { useState } from 'react'

import { useTranslation } from '../hooks/useTranslation.js'
import { api, dataValue, evidenceText, fmtBig, fmtNum, fmtPct } from '../lib/api.js'
import {
  VALUATION_FIELDS,
  valuationFormValues,
  valuationRequest,
} from '../lib/valuation.js'


const SCENARIO_KEYS = {
  conservative: 'valuationConservative',
  base: 'valuationBase',
  optimistic: 'valuationOptimistic',
}

const METHOD_KEYS = {
  trailing_pe: 'valuationTrailingPe',
  price_to_sales: 'valuationPriceSales',
}


function money(point, locale, currency) {
  const value = dataValue(point)
  if (!Number.isFinite(Number(value))) return '—'
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(value)
  } catch {
    return `${currency} ${Number(value).toLocaleString(locale, { maximumFractionDigits: 2 })}`
  }
}


function ScenarioCard({ scenario, locale, currency, t }) {
  const dcf = scenario.dcf
  return (
    <article className={`valuation-scenario ${scenario.scenario}`}>
      <span>{t(SCENARIO_KEYS[scenario.scenario])}</span>
      <strong>{money(dcf.intrinsic_value_per_share, locale, currency)}</strong>
      <small>{fmtPct(dcf.upside_downside, locale)}</small>
      <dl>
        <div><dt>{t('valuationRevenueGrowth')}</dt><dd>{fmtPct(dcf.assumptions.revenue_growth, locale)}</dd></div>
        <div><dt>{t('valuationFcfMargin')}</dt><dd>{fmtPct(dcf.assumptions.free_cash_flow_margin, locale)}</dd></div>
        <div><dt>{t('valuationDiscountRate')}</dt><dd>{fmtPct(dcf.assumptions.discount_rate, locale)}</dd></div>
        <div><dt>{t('valuationTerminalGrowth')}</dt><dd>{fmtPct(dcf.assumptions.terminal_growth, locale)}</dd></div>
      </dl>
    </article>
  )
}


export default function ValuationPanel({ valuation, ticker, onChange }) {
  const { t, ts, locale } = useTranslation()
  const [form, setForm] = useState(() => valuationFormValues(valuation))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  if (!valuation || !form) return null
  const currency = valuation.currency || 'USD'
  const base = valuation.base_case
  const scenarioRange = valuation.margin_of_safety_range

  function updateField(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function recalculate(event) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const assumptions = valuationRequest(form)
      const updated = await api.valuation.calculate(ticker, assumptions)
      setForm(valuationFormValues(updated))
      onChange(updated)
    } catch (requestError) {
      setError(requestError.message.match(/^[a-z_]+$/) ? t('valuationInvalidInput') : requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card valuation-card">
      <div className="valuation-heading">
        <div>
          <p className="card-kicker">{t('valuationKicker')}</p>
          <h3>{t('valuationTitle')}</h3>
          <p>{t('valuationIntro')}</p>
        </div>
        <span className="code-calculated">ƒ(x) · code</span>
      </div>

      <div className="valuation-summary">
        <article>
          <span>{t('valuationIntrinsic')}</span>
          <strong>{money(base.intrinsic_value_per_share, locale, currency)}</strong>
        </article>
        <article>
          <span>{t('valuationCurrentPrice')}</span>
          <strong>{money(base.current_price, locale, currency)}</strong>
        </article>
        <article>
          <span>{t('valuationUpsideDownside')}</span>
          <strong className={dataValue(base.upside_downside) >= 0 ? 'positive' : 'negative'}>
            {fmtPct(base.upside_downside, locale)}
          </strong>
        </article>
        <article>
          <span>{t('valuationScenarioRange')}</span>
          <strong>{money(scenarioRange.low, locale, currency)}–{money(scenarioRange.high, locale, currency)}</strong>
        </article>
      </div>

      <div className="valuation-workbench">
        <form className="valuation-form" onSubmit={recalculate}>
          <div>
            <h4>{t('valuationAssumptionsTitle')}</h4>
            <p>{t('valuationAssumptionsHint')}</p>
          </div>
          <div className="valuation-input-grid">
            <label>
              <span>{t('valuationProjectionYears')}</span>
              <input
                type="number"
                min="3"
                max="10"
                step="1"
                value={form.projection_years}
                onChange={(event) => updateField('projection_years', event.target.value)}
              />
            </label>
            {VALUATION_FIELDS.map((field) => (
              <label key={field.key}>
                <span>{t(field.labelKey)}</span>
                <div>
                  <input
                    type="number"
                    min={field.min}
                    max={field.max}
                    step={field.step}
                    value={form[field.key]}
                    onChange={(event) => updateField(field.key, event.target.value)}
                  />
                  <i>%</i>
                </div>
              </label>
            ))}
          </div>
          {error && <p className="valuation-error" role="alert">{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? t('valuationCalculating') : t('valuationRecalculate')}
          </button>
        </form>

        <div className="valuation-reverse">
          <p className="card-kicker">{t('valuationReverseTitle')}</p>
          <h4>{t('valuationImpliedGrowth')}</h4>
          <strong>
            {valuation.reverse_dcf.converged
              ? fmtPct(valuation.reverse_dcf.implied_revenue_growth, locale)
              : '—'}
          </strong>
          <p>{valuation.reverse_dcf.converged
            ? ts(evidenceText(valuation.reverse_dcf.explanation))
            : t('valuationReverseUnavailable')}</p>
        </div>
      </div>

      <section className="valuation-section">
        <h4>{t('valuationScenariosTitle')}</h4>
        <div className="valuation-scenarios">
          {valuation.scenarios.map((scenario) => (
            <ScenarioCard
              key={scenario.scenario}
              scenario={scenario}
              locale={locale}
              currency={currency}
              t={t}
            />
          ))}
        </div>
      </section>

      <section className="valuation-section">
        <h4>{t('valuationPeerTitle')}</h4>
        {valuation.peer_multiples.length === 0 ? (
          <p className="valuation-empty">{t('valuationPeerUnavailable')}</p>
        ) : (
          <div className="valuation-peers">
            {valuation.peer_multiples.map((estimate) => (
              <article key={estimate.method}>
                <header>
                  <strong>{t(METHOD_KEYS[estimate.method])}</strong>
                  <span>{estimate.sample_size} {t('valuationPeers')}</span>
                </header>
                <dl>
                  <div><dt>{t('valuationMedianMultiple')}</dt><dd>{fmtNum(estimate.peer_median_multiple, locale)}x</dd></div>
                  <div><dt>{t('valuationCompanyBasis')}</dt><dd>{money(estimate.company_basis, locale, currency)}</dd></div>
                  <div><dt>{t('valuationImpliedValue')}</dt><dd>{money(estimate.implied_value_per_share, locale, currency)}</dd></div>
                </dl>
                <small>{estimate.peer_tickers.join(' · ')}</small>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="valuation-section">
        <h4>{t('valuationSensitivityTitle')}</h4>
        <p className="valuation-section-hint">{t('valuationSensitivityHint')}</p>
        <div className="valuation-table-wrap">
          <table className="valuation-sensitivity-table">
            <thead>
              <tr>
                <th>{t('valuationDiscountRow')}</th>
                {valuation.sensitivity.terminal_growth_rates.map((rate) => (
                  <th key={dataValue(rate)}>{fmtPct(rate, locale)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {valuation.sensitivity.rows.map((row) => (
                <tr key={dataValue(row.discount_rate)}>
                  <th>{fmtPct(row.discount_rate, locale)}</th>
                  {row.cells.map((cell) => (
                    <td key={dataValue(cell.terminal_growth)}>
                      {money(cell.intrinsic_value_per_share, locale, currency)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <details className="valuation-projection">
        <summary>{t('valuationProjectionTitle')}</summary>
        <div className="valuation-table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('valuationYear')}</th>
                <th>{t('valuationRevenue')}</th>
                <th>{t('valuationFcf')}</th>
                <th>{t('valuationDilutedShares')}</th>
                <th>{t('valuationPresentValue')}</th>
              </tr>
            </thead>
            <tbody>
              {base.projections.map((projection) => (
                <tr key={projection.year}>
                  <th>{projection.year}</th>
                  <td>{fmtBig(projection.projected_revenue, locale)}</td>
                  <td>{fmtBig(projection.projected_free_cash_flow, locale)}</td>
                  <td>{fmtBig(projection.diluted_shares, locale)}</td>
                  <td>{fmtBig(projection.present_value, locale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <details className="valuation-methodology">
        <summary>{t('valuationMethodology')}</summary>
        <p>{ts(evidenceText(valuation.methodology))}</p>
        <ul>
          {valuation.limitations.map((item, index) => (
            <li key={`${evidenceText(item)}-${index}`}>{ts(evidenceText(item))}</li>
          ))}
        </ul>
        <small>{valuation.disclaimer}</small>
      </details>
    </section>
  )
}
