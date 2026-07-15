export default function NewsFeed({ news }) {
  return (
    <section className="card">
      <h3>Recent news</h3>
      {news.ai_summary && (
        <div className="ai-note">
          <strong>Themes:</strong> {news.ai_summary}
        </div>
      )}
      {news.items.length === 0 && <p className="muted">No recent headlines found.</p>}
      <ul className="news-list">
        {news.items.map((n, i) => (
          <li key={i}>
            {n.link ? (
              <a href={n.link} target="_blank" rel="noreferrer">{n.title}</a>
            ) : (
              n.title
            )}
            <span className="muted news-meta">
              {[n.publisher, n.published_at?.slice(0, 10)].filter(Boolean).join(' · ')}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
