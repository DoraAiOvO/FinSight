import { fmtBig, fmtNum, fmtPct } from '../lib/api.js'

const METRICS = [
  ['market_cap', 'Market cap', fmtBig],
  ['trailing_pe', 'Trailing P/E', fmtNum],
  ['forward_pe', 'Forward P/E', fmtNum],
  ['price_to_sales', 'Price / Sales', fmtNum],
  ['profit_margin', 'Net margin', fmtPct],
  ['revenue_growth', 'Revenue growth', fmtPct],
  ['debt_to_equity', 'Debt / Equity', (v) => (v == null ? '—' : v.toFixed(0) + '%')],
  ['free_cash_flow', 'Free cash flow', fmtBig],
  ['dividend_yield', 'Dividend yield', fmtPct],
  ['beta', 'Beta', fmtNum],
]

export default function StockOverview({ overview: o }) {
  const up = (o.change_percent ?? 0) >= 0
  return (
    <section className="card overview">
      <div className="overview-head">
        <div>
          <h2>
            {o.name || o.ticker} <span className="ticker-chip">{o.ticker}</span>
          </h2>
          <p className="muted">
            {[o.sector, o.industry].filter(Boolean).join(' · ') || '—'}
          </p>
        </div>
        <div className="price-block">
          <div className="price">
            {o.price != null ? `${fmtNum(o.price)} ${o.currency || ''}` : '—'}
          </div>
          {o.change_percent != null && (
            <div className={up ? 'delta up' : 'delta down'}>
              {up ? '▲' : '▼'} {Math.abs(o.change_percent).toFixed(2)}%
            </div>
          )}
        </div>
      </div>
      <div className="metric-grid">
        {METRICS.map(([key, label, fmt]) => (
          <div className="metric" key={key}>
            <span className="metric-label">{label}</span>
            <span className="metric-value">{fmt(o[key])}</span>
          </div>
        ))}
      </div>
      {o.summary && <p className="summary">{o.summary}…</p>}
    </section>
  )
}
