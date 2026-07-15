import { fmtBig, fmtNum, fmtPct } from '../lib/api.js'

const FORMATTERS = {
  market_cap: fmtBig,
  free_cash_flow: fmtBig,
  revenue_growth: fmtPct,
  profit_margin: fmtPct,
  operating_margin: fmtPct,
  dividend_yield: fmtPct,
  debt_to_equity: (value) => (value == null ? '—' : `${value.toFixed(0)}%`),
}

export default function CompareTable({ data }) {
  return (
    <section className="card compare-card">
      <div className="section-heading compare-heading">
        <div>
          <p className="card-kicker">Consistent criteria</p>
          <h2>Side-by-side fundamentals</h2>
        </div>
        <div className="ticker-list">
          {data.tickers.map((ticker) => <span key={ticker}>{ticker}</span>)}
        </div>
      </div>
      <div className="comparison-note">
        <span>★</span>
        Stronger marks the favorable direction for this metric—not the “better stock.”
      </div>
      <div className="table-wrap">
        <table className="compare">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {data.tickers.map((ticker) => <th scope="col" key={ticker}>{ticker}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => {
              const format = FORMATTERS[row.metric] || fmtNum
              return (
                <tr key={row.metric}>
                  <th scope="row">
                    {row.label}
                    {row.higher_is_better != null && (
                      <small>{row.higher_is_better ? 'Higher is favorable' : 'Lower is favorable'}</small>
                    )}
                  </th>
                  {data.tickers.map((ticker) => (
                    <td key={ticker} className={row.best === ticker ? 'best mono' : 'mono'}>
                      {format(row.values[ticker])}
                      {row.best === ticker && <span className="best-mark" aria-label="Stronger value">★</span>}
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
