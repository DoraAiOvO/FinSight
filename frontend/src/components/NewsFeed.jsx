import { useTranslation } from '../hooks/useTranslation.js'

export default function NewsFeed({ news }) {
  const { t, locale } = useTranslation()

  function formatDate(value) {
    if (!value) return null
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value.slice(0, 10)
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(date)
  }
  return (
    <section className="card news-card">
      <div className="section-heading">
        <div>
          <p className="card-kicker">{t('newsKicker')}</p>
          <h3>{t('newsTitle')}</h3>
        </div>
        <span className="source-count">{news.items.length} {t('sources')}</span>
      </div>

      {news.ai_summary && (
        <div className="ai-note">
          <span className="ai-label">{t('headlineThemes')}</span>
          <p>{news.ai_summary}</p>
        </div>
      )}

      {news.items.length === 0 && <p className="empty-copy">{t('noHeadlines')}</p>}
      <ol className="news-list">
        {news.items.map((item, index) => (
          <li key={`${item.title}-${index}`}>
            <span className="news-index">{String(index + 1).padStart(2, '0')}</span>
            <div>
              {item.link ? (
                <a href={item.link} target="_blank" rel="noreferrer">
                  {item.title}<span aria-hidden="true">↗</span>
                </a>
              ) : (
                <span className="news-title">{item.title}</span>
              )}
              <span className="news-meta">
                {[item.publisher, formatDate(item.published_at)].filter(Boolean).join(' · ')}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
