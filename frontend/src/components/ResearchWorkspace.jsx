import { useEffect, useMemo, useState } from 'react'

import { useTranslation } from '../hooks/useTranslation.js'
import { api } from '../lib/api.js'
import {
  buildResearchSnapshot,
  CHANGE_SECTIONS,
  changeDirectionKey,
  changeItemTitle,
  metricDisplay,
  visibleChanges,
} from '../lib/researchWorkspace.js'


function ChangeDetails({ sectionKey, item, locale, t }) {
  if (sectionKey === 'financial_metrics') {
    return (
      <span>{metricDisplay(item.previous, locale)} <b>→</b> {metricDisplay(item.current, locale)}</span>
    )
  }
  if (sectionKey === 'news') {
    return <span>{item.item?.publisher || t('unknownSource')} · {item.item?.published_at || '—'}</span>
  }
  if (sectionKey === 'filings') {
    return <span>{item.filing?.description || item.accession_number}</span>
  }
  if (sectionKey === 'thesis_assumptions') {
    return <span>{item.previous_status || '—'} <b>→</b> {item.current_status || '—'}</span>
  }
  return (
    <span>{item.previous_severity || '—'} <b>→</b> {item.current_severity || '—'}</span>
  )
}


function ChangeSection({ report, section, locale, t, ts }) {
  const items = visibleChanges(section.key, report[section.key])
  return (
    <section className="change-section">
      <div className="change-section-title">
        <h4>{t(section.titleKey)}</h4>
        <span>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="change-empty">{t('noMeaningfulChanges')}</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.metric_key || item.change_key || item.accession_number || item.code}>
              <div>
                <strong>{ts(changeItemTitle(section.key, item))}</strong>
                <ChangeDetails sectionKey={section.key} item={item} locale={locale} t={t} />
              </div>
              <em className={`change-badge ${item.direction}`}>
                {t(changeDirectionKey(item.direction))}
              </em>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}


export default function ResearchWorkspace({ customerId, data, onAnalyze, onRequireProfile }) {
  const { t, ts, language, locale } = useTranslation()
  const [watchlists, setWatchlists] = useState([])
  const [sessions, setSessions] = useState([])
  const [changeReport, setChangeReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [action, setAction] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [creatingWatchlist, setCreatingWatchlist] = useState(false)
  const [newWatchlistName, setNewWatchlistName] = useState('')
  const ticker = data?.overview?.ticker
  const snapshot = useMemo(() => (
    data?.overview ? buildResearchSnapshot(data) : null
  ), [data])

  useEffect(() => {
    if (!customerId || !ticker || !snapshot) {
      setWatchlists([])
      setSessions([])
      setChangeReport(null)
      return undefined
    }
    let active = true
    setLoading(true)
    setError(null)
    Promise.allSettled([
      api.watchlists.list(customerId),
      api.researchSessions.list(customerId, ticker, 6),
      api.researchSessions.whatChanged(customerId, ticker, snapshot),
    ]).then(([watchlistResult, sessionResult, changesResult]) => {
      if (!active) return
      if (watchlistResult.status === 'fulfilled') setWatchlists(watchlistResult.value)
      if (sessionResult.status === 'fulfilled') setSessions(sessionResult.value)
      if (changesResult.status === 'fulfilled') setChangeReport(changesResult.value)
      const failure = [watchlistResult, sessionResult, changesResult]
        .find((result) => result.status === 'rejected')
      setError(failure?.reason?.message || null)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [customerId, ticker, snapshot])

  const defaultWatchlist = watchlists.find((watchlist) => watchlist.is_default) || watchlists[0]
  const isDefaultTracked = defaultWatchlist?.items.some((item) => item.ticker === ticker)

  async function toggleTicker(watchlist = defaultWatchlist) {
    if (!customerId) {
      onRequireProfile()
      return
    }
    setAction(`watchlist:${watchlist?.id || 'new'}`)
    setError(null)
    setNotice(null)
    try {
      let target = watchlist
      if (!target) {
        target = await api.watchlists.create(customerId, {
          name: t('defaultWatchlistName'),
          is_default: true,
        })
      }
      const tracked = target.items.some((item) => item.ticker === ticker)
      const updated = tracked
        ? await api.watchlists.removeItem(customerId, target.id, ticker)
        : await api.watchlists.addItem(customerId, target.id, { ticker })
      setWatchlists((current) => {
        const exists = current.some((item) => item.id === updated.id)
        return exists
          ? current.map((item) => (item.id === updated.id ? updated : item))
          : [updated, ...current]
      })
      setNotice(tracked ? t('removedFromWatchlist') : t('addedToWatchlist'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAction(null)
    }
  }

  async function createWatchlist(event) {
    event.preventDefault()
    const name = newWatchlistName.trim()
    if (!name) return
    setAction('create-watchlist')
    setError(null)
    try {
      const created = await api.watchlists.create(customerId, { name })
      setWatchlists((current) => [...current, created])
      setNewWatchlistName('')
      setCreatingWatchlist(false)
      setNotice(t('watchlistCreated'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAction(null)
    }
  }

  async function saveResearch() {
    if (!customerId) {
      onRequireProfile()
      return
    }
    setAction('save')
    setError(null)
    setNotice(null)
    try {
      const saved = await api.researchSessions.create(customerId, {
        title: `${ticker} · ${t('savedResearchTitle')}`,
        language,
        snapshot,
      })
      setSessions((current) => [saved, ...current.filter((item) => item.id !== saved.id)].slice(0, 6))
      setNotice(t('researchSaved'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAction(null)
    }
  }

  if (!customerId) {
    return (
      <section className="workspace-card workspace-locked">
        <div>
          <p className="section-kicker">{t('workspaceKicker')}</p>
          <h2>{t('workspaceTitle')}</h2>
          <p>{t('workspaceProfileRequired')}</p>
        </div>
        <button type="button" onClick={onRequireProfile}>{t('setUpResearchProfile')}</button>
      </section>
    )
  }

  return (
    <section className="workspace-card" aria-busy={loading}>
      <div className="workspace-heading">
        <div>
          <p className="section-kicker">{t('workspaceKicker')}</p>
          <h2>{t('workspaceTitle')}</h2>
          <p>{t('workspaceDescription')}</p>
        </div>
        <div className="workspace-actions">
          <button
            className="workspace-secondary"
            type="button"
            disabled={Boolean(action)}
            onClick={() => toggleTicker()}
          >
            {isDefaultTracked ? t('removeDefaultWatchlist') : t('addDefaultWatchlist')}
          </button>
          <button
            className="workspace-primary"
            type="button"
            disabled={Boolean(action)}
            onClick={saveResearch}
          >
            {action === 'save' ? t('savingResearch') : t('saveResearch')}
          </button>
        </div>
      </div>

      {(error || notice) && (
        <p className={error ? 'workspace-message error' : 'workspace-message'} role="status">
          {error || notice}
        </p>
      )}

      <div className="workspace-grid">
        <section className="workspace-panel">
          <div className="workspace-panel-heading">
            <div>
              <h3>{t('watchlistsTitle')}</h3>
              <span>{t('watchlistsHint')}</span>
            </div>
            <button type="button" onClick={() => setCreatingWatchlist((value) => !value)}>
              {t('newWatchlist')}
            </button>
          </div>
          {creatingWatchlist && (
            <form className="watchlist-create" onSubmit={createWatchlist}>
              <input
                aria-label={t('watchlistName')}
                maxLength="120"
                placeholder={t('watchlistNamePlaceholder')}
                value={newWatchlistName}
                onChange={(event) => setNewWatchlistName(event.target.value)}
              />
              <button type="submit" disabled={!newWatchlistName.trim() || Boolean(action)}>
                {t('createWatchlist')}
              </button>
            </form>
          )}
          <div className="watchlist-groups">
            {watchlists.length === 0 ? (
              <p>{t('noWatchlists')}</p>
            ) : watchlists.map((watchlist) => {
              const tracked = watchlist.items.some((item) => item.ticker === ticker)
              return (
                <article key={watchlist.id}>
                  <header>
                    <strong>{watchlist.name}</strong>
                    <button
                      type="button"
                      disabled={Boolean(action)}
                      onClick={() => toggleTicker(watchlist)}
                    >
                      {tracked ? `− ${ticker}` : `+ ${ticker}`}
                    </button>
                  </header>
                  <div>
                    {watchlist.items.length === 0 ? (
                      <span>{t('emptyWatchlist')}</span>
                    ) : watchlist.items.map((item) => (
                      <button type="button" key={item.id} onClick={() => onAnalyze(item.ticker)}>
                        {item.ticker}
                      </button>
                    ))}
                  </div>
                </article>
              )
            })}
          </div>
        </section>

        <section className="workspace-panel">
          <div className="workspace-panel-heading">
            <div>
              <h3>{t('savedResearchSessions')}</h3>
              <span>{t('savedResearchHint')}</span>
            </div>
          </div>
          <ol className="research-session-list">
            {sessions.length === 0 ? (
              <li className="empty-session">{t('noSavedResearch')}</li>
            ) : sessions.map((session) => (
              <li key={session.id}>
                <span />
                <div>
                  <strong>{session.title || `${session.ticker} ${t('savedResearchTitle')}`}</strong>
                  <small>{new Date(session.completed_at || session.created_at).toLocaleString(locale, {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })}</small>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <section className="changes-report">
        <div className="changes-heading">
          <div>
            <p className="section-kicker">{t('whatChangedKicker')}</p>
            <h3>{t('whatChangedTitle')}</h3>
          </div>
          {changeReport?.has_baseline && (
            <span>{t('comparedWith')} {new Date(
              changeReport.baseline_session.completed_at || changeReport.baseline_session.created_at,
            ).toLocaleDateString(locale, { dateStyle: 'medium' })}</span>
          )}
        </div>
        {loading && !changeReport ? (
          <p className="changes-placeholder">{t('checkingChanges')}</p>
        ) : !changeReport?.has_baseline ? (
          <div className="changes-placeholder">
            <strong>{t('noResearchBaseline')}</strong>
            <span>{t('saveBaselineExplanation')}</span>
          </div>
        ) : (
          <>
            <div className="change-summary">
              {['new', 'improved', 'worsened', 'changed', 'resolved'].map((direction) => (
                <span className={direction} key={direction}>
                  <strong>{changeReport.summary[direction]}</strong>
                  {t(changeDirectionKey(direction))}
                </span>
              ))}
            </div>
            <div className="change-grid">
              {CHANGE_SECTIONS.map((section) => (
                <ChangeSection
                  key={section.key}
                  report={changeReport}
                  section={section}
                  locale={locale}
                  t={t}
                  ts={ts}
                />
              ))}
            </div>
          </>
        )}
      </section>
    </section>
  )
}
