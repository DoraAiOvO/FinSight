export default function NewsFeed({ news }) {
  return (
    <section className="card news-card">
      <div className="section-heading">
        <div>
          <p className="card-kicker">What is changing</p>
          <h3>Recent news</h3>
        </div>
        <span className="source-count">{news.items.length} sources</span>
      </div>

      {news.ai_summary && (
        <div className="ai-note">
          <span className="ai-label">Headline themes</span>
          <p>{news.ai_summary}</p>
        </div>
      )}

      {news.items.length === 0 && <p className="empty-copy">No recent headlines were found.</p>}
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
                {[item.publisher, item.published_at?.slice(0, 10)].filter(Boolean).join(' · ')}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
