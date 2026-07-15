import { fmtBig, fmtNum, fmtPct } from '../lib/api.js'

const FORMATTERS = {
  market_cap: fmtBig,
  free_cash_flow: fmtBig,
  revenue_growth: fmtPct,
  profit_margin: fmtPct,
  operating_margin: fmtPct,
  dividend_yield: fmtPct,
  debt_to_equity: (v) => (v == null ? '—' : v.toFixed(0) + '%'),
}

export default function CompareTable({ data }) {
  return (
    <section className="card">
      <h3>Side-by-side comparison</h3>
      <p className="muted">
        ★ marks the stronger number for metrics where direction is clear. A “win” on one
        metric is evidence, not a verdict.
      </p>
      <div className="table-wrap">
        <table className="compare">
          <thead>
            <tr>
              <th>Metric</th>
              {data.tickers.map((t) => <th key={t}>{t}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => {
              const fmt = FORMATTERS[row.metric] || fmtNum
              return (
                <tr key={row.metric}>
                  <td>{row.label}</td>
                  {data.tickers.map((t) => (
                    <td key={t} className={row.best === t ? 'best mono' : 'mono'}>
                      {fmt(row.values[t])} {row.best === t && '★'}
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
