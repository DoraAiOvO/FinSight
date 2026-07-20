import { useEffect, useRef, useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'
import { api, evidenceText } from '../lib/api.js'

function FilingDate({ value, locale }) {
  if (!value) return '—'
  const parsed = new Date(`${value}T00:00:00Z`)
  return parsed.toLocaleDateString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

function FilingDetail({ detail, ticker, language, onClose }) {
  const { t } = useTranslation()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [asking, setAsking] = useState(false)
  const [questionError, setQuestionError] = useState(null)

  async function submitQuestion(event) {
    event.preventDefault()
    const normalized = question.trim()
    if (normalized.length < 3) return
    setAsking(true)
    setQuestionError(null)
    setAnswer(null)
    try {
      setAnswer(await api.askFiling(
        ticker,
        detail.filing.accession_number,
        normalized,
        language,
      ))
    } catch (error) {
      setQuestionError(error.message)
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="filing-reader">
      <div className="filing-reader-head">
        <div>
          <span className="filing-type">{detail.filing.filing_type}</span>
          <strong>{detail.filing.description || t('filingDocument')}</strong>
        </div>
        <button type="button" onClick={onClose} aria-label={t('closeFiling')}>×</button>
      </div>

      <div className="filing-sections">
        {detail.sections.map((section, index) => (
          <details
            key={section.section_id}
            open={index === 0 || answer?.citations.some((citation) => citation.section_id === section.section_id)}
            id={section.section_id}
          >
            <summary>
              <span>{section.item === 'filing' ? '' : `${t('filingItem')} ${section.item}`}</span>
              <strong>{section.title}</strong>
              <i aria-hidden="true">+</i>
            </summary>
            <div className="filing-section-body">
              <p>{section.text}</p>
              {section.truncated && <small>{t('sectionTruncated')}</small>}
              <a href={section.source_url} target="_blank" rel="noreferrer">
                {t('openOriginalSection')} ↗
              </a>
            </div>
          </details>
        ))}
      </div>

      <form className="filing-question" onSubmit={submitQuestion}>
        <label htmlFor={`filing-question-${detail.filing.accession_number}`}>
          {t('askThisFiling')}
        </label>
        <div>
          <input
            id={`filing-question-${detail.filing.accession_number}`}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={t('filingQuestionPlaceholder')}
            maxLength={500}
          />
          <button type="submit" disabled={asking || question.trim().length < 3}>
            {asking ? t('askingFiling') : t('askFilingCta')}
          </button>
        </div>
      </form>

      {questionError && <p className="filing-error" role="alert">{questionError}</p>}
      {answer && (
        <div className="filing-answer" aria-live="polite">
          <div className="filing-answer-label">
            <strong>{t('filingAnswer')}</strong>
            <span>{answer.ai_used ? t('aiGroundedAnswer') : t('extractiveAnswer')}</span>
          </div>
          <p>{evidenceText(answer.answer)}</p>
          <ol>
            {answer.citations.map((citation) => (
              <li key={`${citation.section_id}-${citation.quote}`}>
                <a href={`#${citation.section_id}`}>{citation.section_title}</a>
                <blockquote>{citation.quote}</blockquote>
                <a href={citation.source_url} target="_blank" rel="noreferrer">
                  {t('verifyOnSec')} ↗
                </a>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}

export default function FilingsPanel({ data, ticker }) {
  const { t, language, locale } = useTranslation()
  const [selectedAccession, setSelectedAccession] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const detailRequestId = useRef(0)

  useEffect(() => {
    detailRequestId.current += 1
    setSelectedAccession(null)
    setDetail(null)
    setError(null)
  }, [ticker])

  async function readFiling(accessionNumber) {
    if (selectedAccession === accessionNumber) {
      detailRequestId.current += 1
      setSelectedAccession(null)
      setDetail(null)
      setLoading(false)
      return
    }
    const currentRequest = ++detailRequestId.current
    setSelectedAccession(accessionNumber)
    setLoading(true)
    setError(null)
    setDetail(null)
    try {
      const response = await api.filing(ticker, accessionNumber)
      if (currentRequest === detailRequestId.current) setDetail(response)
    } catch (requestError) {
      if (currentRequest === detailRequestId.current) setError(requestError.message)
    } finally {
      if (currentRequest === detailRequestId.current) setLoading(false)
    }
  }

  const fetchedAt = new Date(data.cache.fetched_at)

  return (
    <section className="card filings-card" aria-labelledby="filings-title">
      <div className="section-heading filings-heading">
        <div>
          <p className="card-kicker">{t('filingsKicker')}</p>
          <h2 id="filings-title">{t('filingsTitle')}</h2>
        </div>
        <div className="filings-source-time">
          <span>{t('secOfficialSource')}</span>
          <small>
            {t(data.cache.hit ? 'cacheUpdated' : 'sourceFetched')} {' '}
            {fetchedAt.toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' })}
          </small>
        </div>
      </div>

      {data.filings.length === 0 ? (
        <p className="empty-copy">{t('noFilings')}</p>
      ) : (
        <div className="filing-list">
          {data.filings.map((filing) => (
            <article
              className={selectedAccession === filing.accession_number ? 'selected' : ''}
              key={filing.accession_number}
            >
              <div className="filing-list-main">
                <span className="filing-type">{filing.filing_type}</span>
                <div>
                  <strong>{filing.description || t('filingDocument')}</strong>
                  <small>
                    <FilingDate value={filing.filing_date} locale={locale} />
                    {filing.report_date && <> · {t('periodEnded')} <FilingDate value={filing.report_date} locale={locale} /></>}
                  </small>
                </div>
              </div>
              <div className="filing-list-actions">
                {filing.is_earnings_related && <span className="earnings-badge">{t('earningsRelated')}</span>}
                <a href={filing.source_url} target="_blank" rel="noreferrer" aria-label={t('openOriginalFiling')}>SEC ↗</a>
                <button type="button" onClick={() => readFiling(filing.accession_number)}>
                  {selectedAccession === filing.accession_number && detail
                    ? t('closeSections')
                    : t('readSections')}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {loading && <p className="filing-loading" role="status">{t('loadingFiling')}</p>}
      {error && <p className="filing-error" role="alert">{error}</p>}
      {detail && (
        <FilingDetail
          key={detail.filing.accession_number}
          detail={detail}
          ticker={ticker}
          language={language}
          onClose={() => {
            setSelectedAccession(null)
            setDetail(null)
          }}
        />
      )}
    </section>
  )
}
