import { useEffect, useRef, useState } from 'react'
import { useTranslation } from '../hooks/useTranslation.js'
import { api } from '../lib/api.js'
import { assistantUi } from '../lib/assistant.js'

let nextMessageId = 0
const messageId = () => `assistant-message-${++nextMessageId}`
const safeSourceUrl = (value) => (
  typeof value === 'string' && /^https?:\/\//i.test(value) ? value : null
)

export default function AssistantWidget({ customerId = null, currentReport = null }) {
  const { language } = useTranslation()
  const copy = assistantUi(language)
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(null)
  const [online, setOnline] = useState(() => (
    typeof navigator === 'undefined' ? true : navigator.onLine
  ))
  const triggerRef = useRef(null)
  const inputRef = useRef(null)
  const transcriptRef = useRef(null)

  useEffect(() => {
    function handleOnline() { setOnline(true) }
    function handleOffline() { setOnline(false) }
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  useEffect(() => {
    setMessages((current) => (
      current.length === 1 && current[0].kind === 'greeting'
        ? [{ ...current[0], content: copy.greeting }]
        : current
    ))
  }, [language, copy.greeting])

  useEffect(() => {
    if (!open) return undefined
    inputRef.current?.focus()
    function onKeyDown(event) {
      if (event.key === 'Escape') closePanel()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open])

  useEffect(() => {
    if (!open) return
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [messages, pending, open])

  function openPanel() {
    if (!messages.length) {
      setMessages([{
        id: messageId(), role: 'assistant', kind: 'greeting',
        content: copy.greeting, citations: [],
      }])
    }
    setOpen(true)
  }

  function closePanel() {
    setOpen(false)
    window.requestAnimationFrame(() => triggerRef.current?.focus())
  }

  async function requestReply(text, history) {
    if (!online || pending) return
    setPending(true)
    setFailed(null)
    try {
      const result = await api.assistant.chat({
        message: text,
        history: history.slice(-30).map(({ role, content }) => ({ role, content })),
        website_language: language,
        ...(customerId ? { customer_id: customerId } : {}),
        ...(currentReport ? { current_report: currentReport } : {}),
      })
      setMessages((current) => [...current, {
        id: messageId(),
        role: 'assistant',
        content: result.reply,
        citations: result.citations || [],
        intent: result.intent,
      }])
    } catch (error) {
      setFailed({ text, history, detail: error.message })
    } finally {
      setPending(false)
      window.requestAnimationFrame(() => inputRef.current?.focus())
    }
  }

  function send(text = draft) {
    const normalized = text.trim()
    if (!normalized || pending || !online || normalized.length > 2000) return
    const history = messages
    setMessages((current) => [...current, {
      id: messageId(), role: 'user', content: normalized, citations: [],
    }])
    setDraft('')
    requestReply(normalized, history)
  }

  function onSubmit(event) {
    event.preventDefault()
    send()
  }

  function onInputKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  return (
    <div className="assistant-widget">
      {open && (
        <section
          id="finsight-assistant-panel"
          className="assistant-panel"
          role="dialog"
          aria-labelledby="assistant-title"
          aria-describedby="assistant-disclaimer"
        >
          <header className="assistant-head">
            <span className="assistant-avatar" aria-hidden="true"><i /><i /><i /></span>
            <div>
              <h2 id="assistant-title">{copy.title}</h2>
              <p><span />{copy.subtitle}</p>
            </div>
            <button type="button" className="assistant-close" onClick={closePanel} aria-label={copy.close}>
              <span aria-hidden="true">×</span>
            </button>
          </header>

          {currentReport && (
            <div className="assistant-context" title={currentReport.company_name || currentReport.ticker}>
              <span aria-hidden="true">◎</span>
              {copy.current}: <strong>{currentReport.company_name || currentReport.ticker}</strong>
            </div>
          )}

          <div className="assistant-transcript" ref={transcriptRef} aria-live="polite" aria-busy={pending}>
            {messages.map((message) => (
              <article className={`assistant-message ${message.role}`} key={message.id}>
                <span className="assistant-message-label">
                  {message.role === 'assistant' ? 'FinSight' : copy.you}
                </span>
                <div className="assistant-bubble">{message.content}</div>
                {message.citations?.length > 0 && (
                  <details className="assistant-citations">
                    <summary>{copy.evidence} · {message.citations.length}</summary>
                    <ol>
                      {message.citations.map((citation) => (
                        <li key={citation.evidence_id}>
                          {safeSourceUrl(citation.source_url) ? (
                            <a href={safeSourceUrl(citation.source_url)} target="_blank" rel="noreferrer">
                              {citation.title}
                            </a>
                          ) : <strong>{citation.title}</strong>}
                          <span>{citation.source}{citation.as_of_date ? ` · ${citation.as_of_date}` : ''}</span>
                        </li>
                      ))}
                    </ol>
                  </details>
                )}
              </article>
            ))}

            {messages.length === 1 && !pending && (
              <div className="assistant-suggestions" aria-label={copy.suggestions}>
                {copy.questions.map((question) => (
                  <button type="button" key={question} onClick={() => send(question)}>{question}</button>
                ))}
              </div>
            )}

            {pending && (
              <div className="assistant-typing" role="status">
                <span className="sr-only">{copy.loading}</span><i /><i /><i />
              </div>
            )}

            {failed && !pending && (
              <div className="assistant-error" role="alert">
                <p>{copy.error}</p>
                <button type="button" onClick={() => requestReply(failed.text, failed.history)}>{copy.retry}</button>
              </div>
            )}
          </div>

          <footer className="assistant-compose">
            {!online && <p className="assistant-offline" role="status">{copy.offline}</p>}
            <form onSubmit={onSubmit}>
              <label className="sr-only" htmlFor="assistant-message-input">{copy.placeholder}</label>
              <textarea
                id="assistant-message-input"
                ref={inputRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value.slice(0, 2000))}
                onKeyDown={onInputKeyDown}
                placeholder={copy.placeholder}
                rows="1"
                maxLength="2000"
                disabled={!online}
              />
              <button type="submit" disabled={!draft.trim() || pending || !online} aria-label={copy.send}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12 20 4l-5 16-3.5-6.5L4 12Zm7.5 1.5L20 4" /></svg>
              </button>
            </form>
            {draft.length > 1600 && <span className="assistant-count">{2000 - draft.length} {copy.chars}</span>}
            <p id="assistant-disclaimer">{copy.disclaimer}</p>
          </footer>
        </section>
      )}

      <button
        ref={triggerRef}
        type="button"
        className={`assistant-trigger ${open ? 'open' : ''}`}
        onClick={open ? closePanel : openPanel}
        aria-label={open ? copy.close : copy.open}
        aria-expanded={open}
        aria-controls="finsight-assistant-panel"
      >
        {open ? <span aria-hidden="true">×</span> : (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5.2 5.7A8.8 8.8 0 0 1 20.5 12a8.7 8.7 0 0 1-9 8.7 9.2 9.2 0 0 1-3.8-.8L3.5 21l1.2-4.1A8.6 8.6 0 0 1 5.2 5.7Z" />
            <path d="M8 12h.01M12 12h.01M16 12h.01" />
          </svg>
        )}
        <span className="assistant-trigger-label">{copy.title}</span>
      </button>
    </div>
  )
}
