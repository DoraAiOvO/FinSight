export default function PriceChart({ history }) {
  const points = history.points
  if (!points || points.length < 2) return null

  const w = 900
  const h = 220
  const pad = 8
  const closes = points.map((p) => p.close)
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const span = max - min || 1

  const path = points
    .map((p, i) => {
      const x = pad + (i / (points.length - 1)) * (w - 2 * pad)
      const y = h - pad - ((p.close - min) / span) * (h - 2 * pad)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const first = closes[0]
  const last = closes[closes.length - 1]
  const up = last >= first
  const changePct = (((last - first) / first) * 100).toFixed(1)

  return (
    <section className="card chart-card">
      <div className="chart-head">
        <h3>Price — last {history.period}</h3>
        <span className={up ? 'delta up' : 'delta down'}>
          {up ? '▲' : '▼'} {Math.abs(changePct)}% over period
        </span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="chart" preserveAspectRatio="none" role="img"
        aria-label={`Price chart from ${points[0].date} to ${points[points.length - 1].date}`}>
        <path d={`${path} L${w - pad},${h - pad} L${pad},${h - pad} Z`}
          fill={up ? 'rgba(52,199,123,0.12)' : 'rgba(255,99,99,0.12)'} stroke="none" />
        <path d={path} fill="none" stroke={up ? '#34c77b' : '#ff6363'} strokeWidth="2" />
      </svg>
      <div className="chart-range muted">
        <span>{points[0].date}</span>
        <span>low {min.toFixed(2)} · high {max.toFixed(2)}</span>
        <span>{points[points.length - 1].date}</span>
      </div>
    </section>
  )
}
