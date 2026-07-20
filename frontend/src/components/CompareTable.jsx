import { fmtBig, fmtNum, fmtPct } from '../lib/api.js'
import { useTranslation } from '../hooks/useTranslation.js'

const FORMATTERS = {
  market_cap: fmtBig,
  free_cash_flow: fmtBig,
  revenue_growth: fmtPct,
  profit_margin: fmtPct,
  operating_margin: fmtPct,
  dividend_yield: fmtPct,
  debt_to_equity: (value, locale) => (
    value == null ? '—' : `${value.toLocaleString(locale, { maximumFractionDigits: 0 })}%`
  ),
}

export default function CompareTable({ data }) {
  const { t, ts, locale } = useTranslation()
  return (
    <section className="card compare-card">
      <div className="section-heading compare-heading">
        <div>
          <p className="card-kicker">{t('compareKicker')}</p>
          <h2>{t('compareTableTitle')}</h2>
        </div>
        <div className="ticker-list">
          {data.tickers.map((ticker) => <span key={ticker}>{ticker}</span>)}
        </div>
      </div>
      <div className="comparison-note">
        <span>★</span>
        {t('compareNote')}
      </div>
      <div className="table-wrap">
        <table className="compare">
          <thead>
            <tr>
              <th scope="col">{t('metricHeader')}</th>
              {data.tickers.map((ticker) => <th scope="col" key={ticker}>{ticker}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => {
              const format = FORMATTERS[row.metric] || fmtNum
              return (
                <tr key={row.metric}>
                  <th scope="row">
                    {ts(row.label)}
                    {row.higher_is_better != null && (
                      <small>{row.higher_is_better ? t('higherFavorable') : t('lowerFavorable')}</small>
                    )}
                  </th>
                  {data.tickers.map((ticker) => (
                    <td key={ticker} className={row.best === ticker ? 'best mono' : 'mono'}>
                      {format(row.values[ticker], locale)}
                      {row.best === ticker && <span className="best-mark" aria-label={t('strongerValue')}>★</span>}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
