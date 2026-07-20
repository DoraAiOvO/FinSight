import { dataValue, evidenceText, fmtBig, fmtNum, fmtPct } from '../lib/api.js'
import { useTranslation } from '../hooks/useTranslation.js'

const METRICS = [
  ['market_cap', 'mMarketCap', fmtBig],
  ['trailing_pe', 'mTrailingPe', fmtNum],
  ['forward_pe', 'mForwardPe', fmtNum],
  ['price_to_sales', 'mPriceToSales', fmtNum],
  ['profit_margin', 'mNetMargin', fmtPct],
  ['revenue_growth', 'mRevenueGrowth', fmtPct],
  ['debt_to_equity', 'mDebtToEquity', (value, locale) => (
    dataValue(value) == null
      ? '—'
      : `${dataValue(value).toLocaleString(locale, { maximumFractionDigits: 0 })}%`
  )],
  ['free_cash_flow', 'mFreeCashFlow', fmtBig],
]

export default function StockOverview({
  overview: company,
  highlightedMetrics = [],
  industryMatch = false,
}) {
  const { t, locale } = useTranslation()
  const price = dataValue(company.price)
  const changePercent = dataValue(company.change_percent)
  const rangeLow = dataValue(company.fifty_two_week_low)
  const rangeHigh = dataValue(company.fifty_two_week_high)
  const summary = evidenceText(company.summary)
  const isUp = (changePercent ?? 0) >= 0
  const range = rangeHigh - rangeLow
  const rangePosition = range > 0 && price != null
    ? Math.max(0, Math.min(100, ((price - rangeLow) / range) * 100))
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
            {industryMatch && <span className="industry-match">{t('industryInterest')}</span>}
          </div>
        </div>
        <div className="price-block">
          <span className="price-label">{t('currentPrice')}</span>
          <div className="price">
            {price != null ? `${fmtNum(price, locale)} ${company.currency || ''}` : '—'}
          </div>
          {changePercent != null && (
            <div className={isUp ? 'delta up' : 'delta down'}>
              {isUp ? '↗' : '↘'} {Math.abs(changePercent).toLocaleString(locale, {
                maximumFractionDigits: 2,
              })}% {t('today')}
            </div>
          )}
        </div>
      </div>

      <div className="metric-grid">
        {METRICS.map(([key, labelKey, format]) => (
          <div className={highlightedMetrics?.includes(key) ? 'metric profile-highlighted' : 'metric'} key={key}>
            <span className="metric-label">{t(labelKey)}</span>
            <span className="metric-value">{format(company[key], locale)}</span>
            {highlightedMetrics?.includes(key) && (
              <span className="metric-highlight-label">{t('highlightedForProfile')}</span>
            )}
          </div>
        ))}
      </div>

      {(rangePosition != null || summary) && (
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
                <span>{fmtNum(rangeLow, locale)}</span>
                <span>{fmtNum(rangeHigh, locale)}</span>
              </div>
            </div>
          )}
          {summary && <p className="summary">{summary}</p>}
        </div>
      )}
    </section>
  )
}
