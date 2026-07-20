import { fmtBig, fmtNum, fmtPct } from '../lib/api.js'
import { useTranslation } from '../hooks/useTranslation.js'

const METRICS = [
  ['market_cap', 'mMarketCap', fmtBig],
  ['trailing_pe', 'mTrailingPe', fmtNum],
  ['forward_pe', 'mForwardPe', fmtNum],
  ['price_to_sales', 'mPriceToSales', fmtNum],
  ['profit_margin', 'mNetMargin', fmtPct],
  ['revenue_growth', 'mRevenueGrowth', fmtPct],
  ['debt_to_equity', 'mDebtToEquity', (value, locale) => (
    value == null ? '—' : `${value.toLocaleString(locale, { maximumFractionDigits: 0 })}%`
  )],
  ['free_cash_flow', 'mFreeCashFlow', fmtBig],
]

export default function StockOverview({ overview: company }) {
  const { t, locale } = useTranslation()
  const isUp = (company.change_percent ?? 0) >= 0
  const range = company.fifty_two_week_high - company.fifty_two_week_low
  const rangePosition = range > 0 && company.price != null
    ? Math.max(0, Math.min(100, ((company.price - company.fifty_two_week_low) / range) * 100))
    : null

  return (
    <section className="card overview-card">
      <div className="overview-head">
        <div className="company-identity">
          <span className="company-monogram" aria-hidden="true">
            {(company.name || company.ticker).slice(0, 1)}
          </span>
          <div>
            <div className="company-title-line">
              <h2>{company.name || company.ticker}</h2>
              <span className="ticker-chip">{company.ticker}</span>
            </div>
            <p className="muted">
              {[company.sector, company.industry].filter(Boolean).join(' · ') || t('companyProfile')}
            </p>
          </div>
        </div>
        <div className="price-block">
          <span className="price-label">{t('currentPrice')}</span>
          <div className="price">
            {company.price != null ? `${fmtNum(company.price, locale)} ${company.currency || ''}` : '—'}
          </div>
          {company.change_percent != null && (
            <div className={isUp ? 'delta up' : 'delta down'}>
              {isUp ? '↗' : '↘'} {Math.abs(company.change_percent).toLocaleString(locale, {
                maximumFractionDigits: 2,
              })}% {t('today')}
            </div>
          )}
        </div>
      </div>

      <div className="metric-grid">
        {METRICS.map(([key, labelKey, format]) => (
          <div className="metric" key={key}>
            <span className="metric-label">{t(labelKey)}</span>
            <span className="metric-value">{format(company[key], locale)}</span>
          </div>
        ))}
      </div>

      {(rangePosition != null || company.summary) && (
        <div className="overview-context">
          {rangePosition != null && (
            <div className="range-block">
              <div className="range-heading">
                <span>{t('range52')}</span>
                <strong>{rangePosition.toLocaleString(locale, {
                  maximumFractionDigits: 0,
                })}% {t('throughRange')}</strong>
              </div>
              <div className="range-track">
                <span style={{ left: `${rangePosition}%` }} />
              </div>
              <div className="range-values muted">
                <span>{fmtNum(company.fifty_two_week_low, locale)}</span>
                <span>{fmtNum(company.fifty_two_week_high, locale)}</span>
              </div>
            </div>
          )}
          {company.summary && <p className="summary">{company.summary}</p>}
        </div>
      )}
    </section>
  )
}
