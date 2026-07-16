import { useTranslation } from '../hooks/useTranslation.js'

const PERIODS = [
  ['1mo', '1M'],
  ['3mo', '3M'],
  ['6mo', '6M'],
  ['1y', '1Y'],
  ['2y', '2Y'],
  ['5y', '5Y'],
]

export default function PriceChart({ history, loading, onPeriodChange }) {
  const { t } = useTranslation()
  const points = (history.points || []).filter((point) => Number.isFinite(point.close))
  if (!points || points.length < 2) return null

  const width = 900
  const height = 220
  const padding = 8
  const closes = points.map((point) => point.close)
  const minimum = Math.min(...closes)
  const maximum = Math.max(...closes)
  const span = maximum - minimum || 1
  const coords = points.map((point, index) => {
    const x = padding + (index / (points.length - 1)) * (width - 2 * padding)
    const y = height - padding - ((point.close - minimum) / span) * (height - 2 * padding)
    return [x, y]
  })
  const path = coords
    .map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ')

  const first = closes[0]
  const last = closes[closes.length - 1]
  const isUp = last >= first
  const changePercent = ((last - first) / first) * 100
  const gradientId = isUp ? 'chart-fill-up' : 'chart-fill-down'
  const lineColor = isUp ? '#8fe3bd' : '#ff7e84'
  const [endX, endY] = coords[coords.length - 1]

  return (
    <section className={`card chart-card ${loading ? 'is-loading' : ''}`}>
      <div className="chart-head">
        <div>
          <p className="card-kicker">{t('chartKicker')}</p>
          <h3>{t('chartTitle')}</h3>
        </div>
        <div className="period-toggle" aria-label={t('chartPeriodAria')}>
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
          {isUp ? '↗' : '↘'} {Math.abs(changePercent).toFixed(1)}% {t('over')} {history.period}
        </span>
      </div>

      <div className="chart-wrap">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="chart"
          preserveAspectRatio="none"
          role="img"
          aria-label={`${points[0].date} → ${points[points.length - 1].date}`}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor={isUp ? 'rgba(143,227,189,0.28)' : 'rgba(255,126,132,0.26)'}
              />
              <stop
                offset="100%"
                stopColor={isUp ? 'rgba(143,227,189,0)' : 'rgba(255,126,132,0)'}
              />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((fraction) => {
            const y = padding + fraction * (height - 2 * padding)
            return (
              <line
                key={fraction}
                x1={padding}
                x2={width - padding}
                y1={y}
                y2={y}
                stroke="rgba(147,164,159,0.12)"
                strokeDasharray="3 6"
                vectorEffect="non-scaling-stroke"
              />
            )
          })}
          <path
            d={`${path} L${width - padding},${height - padding} L${padding},${height - padding} Z`}
            fill={`url(#${gradientId})`}
            stroke="none"
          />
          <path
            d={path}
            fill="none"
            stroke={lineColor}
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <span
          className={`chart-dot ${isUp ? '' : 'down'}`}
          aria-hidden="true"
          style={{ left: `${(endX / width) * 100}%`, top: `${(endY / height) * 100}%` }}
        />
        {loading && <span className="chart-loading">{t('updatingChart')}</span>}
      </div>
      <div className="chart-range muted">
        <span>{points[0].date}</span>
        <span>{t('low')} {minimum.toFixed(2)} · {t('high')} {maximum.toFixed(2)}</span>
        <span>{points[points.length - 1].date}</span>
      </div>
    </section>
  )
}
