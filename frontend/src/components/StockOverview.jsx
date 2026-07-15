import { fmtBig, fmtNum, fmtPct } from '../lib/api.js'

const METRICS = [
  ['market_cap', 'Market cap', fmtBig],
  ['trailing_pe', 'Trailing P/E', fmtNum],
  ['forward_pe', 'Forward P/E', fmtNum],
  ['price_to_sales', 'Price / Sales', fmtNum],
  ['profit_margin', 'Net margin', fmtPct],
  ['revenue_growth', 'Revenue growth', fmtPct],
  ['debt_to_equity', 'Debt / Equity', (value) => (value == null ? '—' : `${value.toFixed(0)}%`)],
  ['free_cash_flow', 'Free cash flow', fmtBig],
]

export default function StockOverview({ overview: company }) {
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
              {[company.sector, company.industry].filter(Boolean).join(' · ') || 'Company profile'}
            </p>
          </div>
        </div>
        <div className="price-block">
          <span className="price-label">Current price</span>
          <div className="price">
            {company.price != null ? `${fmtNum(company.price)} ${company.currency || ''}` : '—'}
          </div>
          {company.change_percent != null && (
            <div className={isUp ? 'delta up' : 'delta down'}>
              {isUp ? '↗' : '↘'} {Math.abs(company.change_percent).toFixed(2)}% today
            </div>
          )}
        </div>
      </div>

      <div className="metric-grid">
        {METRICS.map(([key, label, format]) => (
          <div className="metric" key={key}>
            <span className="metric-label">{label}</span>
            <span className="metric-value">{format(company[key])}</span>
          </div>
        ))}
      </div>

      {(rangePosition != null || company.summary) && (
        <div className="overview-context">
          {rangePosition != null && (
            <div className="range-block">
              <div className="range-heading">
                <span>52-week range</span>
                <strong>{rangePosition.toFixed(0)}% through range</strong>
              </div>
              <div className="range-track">
                <span style={{ left: `${rangePosition}%` }} />
              </div>
              <div className="range-values muted">
                <span>{fmtNum(company.fifty_two_week_low)}</span>
                <span>{fmtNum(company.fifty_two_week_high)}</span>
              </div>
            </div>
          )}
          {company.summary && <p className="summary">{company.summary}</p>}
        </div>
      )}
    </section>
  )
}
