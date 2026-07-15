const PERIODS = [
  ['1mo', '1M'],
  ['3mo', '3M'],
  ['6mo', '6M'],
  ['1y', '1Y'],
  ['2y', '2Y'],
  ['5y', '5Y'],
]

export default function PriceChart({ history, loading, onPeriodChange }) {
  const points = (history.points || []).filter((point) => Number.isFinite(point.close))
  if (!points || points.length < 2) return null

  const width = 900
  const height = 220
  const padding = 8
  const closes = points.map((point) => point.close)
  const minimum = Math.min(...closes)
  const maximum = Math.max(...closes)
  const span = maximum - minimum || 1
  const path = points
    .map((point, index) => {
      const x = padding + (index / (points.length - 1)) * (width - 2 * padding)
      const y = height - padding - ((point.close - minimum) / span) * (height - 2 * padding)
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const first = closes[0]
  const last = closes[closes.length - 1]
  const isUp = last >= first
  const changePercent = ((last - first) / first) * 100

  return (
    <section className={`card chart-card ${loading ? 'is-loading' : ''}`}>
      <div className="chart-head">
        <div>
          <p className="card-kicker">Market context</p>
          <h3>Price performance</h3>
        </div>
        <div className="period-toggle" aria-label="Price history period">
          {PERIODS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={history.period === value ? 'active' : ''}
              aria-pressed={history.period === value}
              disabled={loading}
              onClick={() => onPeriodChange(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-summary">
        <strong>{last.toFixed(2)}</strong>
        <span className={isUp ? 'delta up' : 'delta down'}>
          {isUp ? '↗' : '↘'} {Math.abs(changePercent).toFixed(1)}% over {history.period}
        </span>
      </div>

      <div className="chart-wrap">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="chart"
          preserveAspectRatio="none"
          role="img"
          aria-label={`Price from ${points[0].date} to ${points[points.length - 1].date}`}
        >
          <path
            d={`${path} L${width - padding},${height - padding} L${padding},${height - padding} Z`}
            fill={isUp ? 'rgba(143,227,189,0.10)' : 'rgba(255,126,132,0.10)'}
            stroke="none"
          />
          <path d={path} fill="none" stroke={isUp ? '#8fe3bd' : '#ff7e84'} strokeWidth="2" />
        </svg>
        {loading && <span className="chart-loading">Updating chart…</span>}
      </div>
      <div className="chart-range muted">
        <span>{points[0].date}</span>
        <span>Low {minimum.toFixed(2)} · High {maximum.toFixed(2)}</span>
        <span>{points[points.length - 1].date}</span>
      </div>
    </section>
  )
}
