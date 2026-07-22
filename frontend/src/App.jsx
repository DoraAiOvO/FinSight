import { useEffect, useMemo, useRef, useState } from 'react'
import SearchBar from './components/SearchBar.jsx'
import StockOverview from './components/StockOverview.jsx'
import PriceChart from './components/PriceChart.jsx'
import AnalysisPanel from './components/AnalysisPanel.jsx'
import BenchmarkPanel from './components/BenchmarkPanel.jsx'
import NewsFeed from './components/NewsFeed.jsx'
import FilingsPanel from './components/FilingsPanel.jsx'
import CompareTable from './components/CompareTable.jsx'
import CustomerOnboarding from './components/CustomerOnboarding.jsx'
import LanguageSwitcher from './components/LanguageSwitcher.jsx'
import PersonalizationBanner from './components/PersonalizationBanner.jsx'
import ProfileButton from './components/ProfileButton.jsx'
import ResearchWorkspace from './components/ResearchWorkspace.jsx'
import ValuationPanel from './components/ValuationPanel.jsx'
import EvidenceAuditPanel from './components/EvidenceAuditPanel.jsx'
import AssistantWidget from './components/AssistantWidget.jsx'
import { useCustomerProfile } from './context/CustomerProfileContext.jsx'
import { useTranslation } from './hooks/useTranslation.js'
import { api } from './lib/api.js'
import { buildAssistantReportContext } from './lib/assistant.js'
import {
  applyAuditResult,
  buildAuditDraft,
  buildComparisonAuditDraft,
} from './lib/evidenceAudit.js'

const STARTER_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'COST']

export function AnalysisViewToggle({ value, onChange }) {
  const { t } = useTranslation()
  return (
    <div className="analysis-view-toggle" aria-label={t('analysisViewAria')}>
      <button
        type="button"
        className={value === 'personalized' ? 'active' : ''}
        aria-pressed={value === 'personalized'}
        onClick={() => onChange('personalized')}
      >
        {t('personalizedView')}
      </button>
      <button
        type="button"
        className={value === 'neutral' ? 'active' : ''}
        aria-pressed={value === 'neutral'}
        onClick={() => onChange('neutral')}
      >
        {t('neutralEvidenceView')}
      </button>
    </div>
  )
}

function ReportSections({ data, historyLoading, onPeriodChange, onValuationChange, researchView }) {
  const interpretation = data.analysis?.personalized_interpretation
  const personalized = researchView === 'personalized'
  const presentation = personalized ? interpretation?.presentation : null
  const neutral = data.analysis?.neutral_evidence
  const sections = {
    overview: (
      <StockOverview
        overview={data.overview}
        highlightedMetrics={presentation?.highlighted_metric_keys}
        industryMatch={presentation?.industry_match}
      />
    ),
    price_history: data.history && (
      <PriceChart
        history={data.history}
        loading={historyLoading}
        onPeriodChange={onPeriodChange}
      />
    ),
    analysis: data.analysis && (
      <AnalysisPanel analysis={data.analysis} personalized={personalized} />
    ),
    benchmarks: neutral?.benchmarks && (
      <BenchmarkPanel benchmarks={neutral.benchmarks} />
    ),
    valuation: data.valuation && (
      <ValuationPanel
        valuation={data.valuation}
        ticker={data.overview.ticker}
        onChange={onValuationChange}
      />
    ),
    news: data.news && <NewsFeed news={data.news} />,
    filings: data.filings && <FilingsPanel data={data.filings} ticker={data.overview.ticker} />,
  }

  if (!presentation?.personalized) {
    return (
      <>
        {sections.overview}
        {sections.price_history}
        {sections.benchmarks}
        {sections.valuation}
        <div className="research-grid">
          {sections.analysis}
          {sections.news}
        </div>
        {sections.filings}
      </>
    )
  }

  return (
    <>
      <div className="personalized-report-sections">
        {presentation.section_order.map((section) => (
          sections[section] ? (
            <div className={`report-section report-section-${section}`} key={section}>
              {section === 'analysis' && sections.benchmarks}
              {sections[section]}
            </div>
          ) : null
        ))}
      </div>
      {sections.valuation}
      {sections.filings}
    </>
  )
}

function LoadingReport({ mode }) {
  const { t } = useTranslation()
  return (
    <main className="results loading-report" aria-live="polite" aria-busy="true">
      <div className="loading-copy">
        <span className="loading-pulse" />
        {mode === 'compare' ? t('loadingCompare') : t('loadingAnalyze')}
      </div>
      <div className="skeleton skeleton-hero" />
      <div className="skeleton-grid">
        <div className="skeleton" />
        <div className="skeleton" />
      </div>
    </main>
  )
}

function EmptyState({ onAnalyze }) {
  const { t } = useTranslation()
  return (
    <main className="landing">
      <section className="hero-copy">
        <p className="eyebrow">{t('eyebrow')}</p>
        <h1>{t('heroTitle')} <em>{t('heroTitleEm')}</em></h1>
        <p className="hero-lede">{t('heroLede')}</p>
        <div className="starter-row" aria-label={t('tryPopular')}>
          <span>{t('startWith')}</span>
          {STARTER_TICKERS.map((ticker) => (
            <button key={ticker} type="button" onClick={() => onAnalyze(ticker)}>
              {ticker}
            </button>
          ))}
        </div>
      </section>

      <section className="method-card" aria-labelledby="method-title">
        <div className="method-topline">
          <span className="method-kicker">{t('methodKicker')}</span>
          <span className="method-badge">{t('methodBadge')}</span>
        </div>
        <h2 id="method-title">{t('methodTitle')}</h2>
        <ol className="method-list">
          <li>
            <span>01</span>
            <div><strong>{t('methodCollect')}</strong><small>{t('methodCollectDesc')}</small></div>
          </li>
          <li>
            <span>02</span>
            <div><strong>{t('methodTest')}</strong><small>{t('methodTestDesc')}</small></div>
          </li>
          <li>
            <span>03</span>
            <div><strong>{t('methodExplain')}</strong><small>{t('methodExplainDesc')}</small></div>
          </li>
        </ol>
      </section>
    </main>
  )
}

export default function App() {
  const { t, language, locale } = useTranslation()
  const { customerId, profile, openOnboarding } = useCustomerProfile()
  const [mode, setMode] = useState('analyze')
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notices, setNotices] = useState([])
  const [data, setData] = useState(null)
  const [compare, setCompare] = useState(null)
  const [compareAudit, setCompareAudit] = useState(null)
  const [researchView, setResearchView] = useState('personalized')
  const requestId = useRef(0)
  const lastAnalyzeTicker = useRef(null)
  const previousPreferenceKey = useRef(`${language}:${profile?.updated_at || ''}`)
  const assistantReport = useMemo(
    () => buildAssistantReportContext(data, compare, language),
    [data, compare, language],
  )

  useEffect(() => {
    const preferenceKey = `${language}:${profile?.updated_at || ''}`
    if (previousPreferenceKey.current === preferenceKey) return
    previousPreferenceKey.current = preferenceKey
    const ticker = data?.overview?.ticker || (
      loading && mode === 'analyze' ? lastAnalyzeTicker.current : null
    )
    if (ticker) analyze(ticker)
  }, [language, profile?.updated_at])

  function changeMode(nextMode) {
    setMode(nextMode)
    setError(null)
  }

  function resetHome() {
    requestId.current += 1
    setLoading(false)
    setHistoryLoading(false)
    setError(null)
    setNotices([])
    setData(null)
    setCompare(null)
    setCompareAudit(null)
    setResearchView('personalized')
    lastAnalyzeTicker.current = null
  }

  function noticeText(notice) {
    return notice.detail ? `${t(notice.key)}: ${notice.detail}` : t(notice.key)
  }

  async function analyze(ticker) {
    lastAnalyzeTicker.current = ticker
    const currentRequest = ++requestId.current
    setMode('analyze')
    setLoading(true)
    setHistoryLoading(false)
    setError(null)
    setNotices([])
    setCompare(null)
    setCompareAudit(null)
    setResearchView('personalized')

    try {
      const overview = await api.overview(ticker)
      const analysisRequest = api.analysis(ticker, language, customerId)
      const sections = await Promise.allSettled([
        api.history(ticker, '6mo'),
        analysisRequest,
        api.news(ticker, language),
        api.filings(ticker),
        analysisRequest.then(
          () => api.valuation.get(ticker),
          () => api.valuation.get(ticker),
        ),
      ])
      if (currentRequest !== requestId.current) return

      const sectionKeys = [
        'noticeHistory',
        'noticeAnalysis',
        'noticeNews',
        'noticeFilings',
        'noticeValuation',
      ]
      const unavailable = sections.flatMap((result, index) =>
        result.status === 'rejected' ? [{ key: sectionKeys[index] }] : [],
      )
      const draft = {
        overview,
        history: sections[0].status === 'fulfilled' ? sections[0].value : null,
        analysis: sections[1].status === 'fulfilled' ? sections[1].value : null,
        news: sections[2].status === 'fulfilled' ? sections[2].value : null,
        filings: sections[3].status === 'fulfilled' ? sections[3].value : null,
        valuation: sections[4].status === 'fulfilled' ? sections[4].value : null,
        generatedAt: new Date(),
      }
      const auditResult = await api.auditReport(buildAuditDraft(draft))
      if (currentRequest !== requestId.current) return
      setNotices(unavailable)
      setData(applyAuditResult(draft, auditResult))
    } catch (requestError) {
      if (currentRequest !== requestId.current) return
      setError(requestError.message)
      setData(null)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }

  async function changePeriod(nextPeriod) {
    if (!data || nextPeriod === data.history?.period) return
    const parentRequest = requestId.current
    setHistoryLoading(true)
    try {
      const history = await api.history(data.overview.ticker, nextPeriod)
      if (parentRequest !== requestId.current) return
      const draft = { ...data, history }
      const auditResult = await api.auditReport(buildAuditDraft(draft))
      if (parentRequest !== requestId.current) return
      setData(applyAuditResult(draft, auditResult))
      setNotices((current) => current.filter((notice) => !notice.key.startsWith('noticeHistory')))
    } catch (requestError) {
      if (parentRequest !== requestId.current) return
      setNotices((current) => [
        ...current.filter((notice) => !notice.key.startsWith('noticeHistory')),
        { key: 'noticeHistoryUpdate', detail: requestError.message },
      ])
    } finally {
      if (parentRequest === requestId.current) setHistoryLoading(false)
    }
  }

  async function runCompare(tickers) {
    const currentRequest = ++requestId.current
    setLoading(true)
    setHistoryLoading(false)
    setError(null)
    setNotices([])
    setData(null)
    setCompare(null)
    setCompareAudit(null)
    try {
      const result = await api.compare(tickers)
      const auditResult = await api.auditReport(buildComparisonAuditDraft(result))
      if (currentRequest === requestId.current) {
        setCompare(auditResult.report.comparison)
        setCompareAudit(auditResult.audit)
      }
    } catch (requestError) {
      if (currentRequest !== requestId.current) return
      setError(requestError.message)
      setCompare(null)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }

  async function updateValuation(valuation) {
    if (!data || data.overview?.ticker !== valuation.ticker) return valuation
    const parentRequest = requestId.current
    const draft = { ...data, valuation }
    const auditResult = await api.auditReport(buildAuditDraft(draft))
    if (parentRequest !== requestId.current) return valuation
    const audited = applyAuditResult(draft, auditResult)
    setData((current) => (
      current?.overview?.ticker === valuation.ticker ? audited : current
    ))
    return audited.valuation
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <button className="brand" type="button" onClick={resetHome} aria-label={t('goHome')}>
          <span className="brand-mark" aria-hidden="true"><i /></span>
          <span>FinSight</span>
        </button>
        <div className="header-actions">
          <div className="header-note">
            <span className="status-dot" />
            {t('headerNote')}
          </div>
          <ProfileButton />
          <LanguageSwitcher />
        </div>
      </header>

      <SearchBar
        mode={mode}
        onModeChange={changeMode}
        onAnalyze={analyze}
        onCompare={runCompare}
        loading={loading}
      />

      {error && (
        <div className="message error-box" role="alert">
          <strong>{t('errorTitle')}</strong>
          <span>{error}</span>
        </div>
      )}

      {notices.length > 0 && !loading && (
        <div className="message notice-box" role="status">
          <strong>{t('partialReport')}</strong>
          <span>{notices.map(noticeText).join(' ')}</span>
        </div>
      )}

      {loading && <LoadingReport mode={mode} />}

      {!loading && data && (
        <main className="results">
          <div className="report-heading">
            <div>
              <p className="eyebrow">{t('researchBriefKicker')} · {data.overview.ticker}</p>
              <h1>{t('reportTitle')} <em>{t('reportTitleEm')}</em></h1>
            </div>
            <p className="report-time">
              {t('generatedAt')} {data.generatedAt.toLocaleTimeString(locale, {
                hour: 'numeric',
                minute: '2-digit',
              })}
              <span>{t('dataDelayed')}</span>
            </p>
          </div>
          {data.analysis && (
            <AnalysisViewToggle value={researchView} onChange={setResearchView} />
          )}
          <PersonalizationBanner
            presentation={
              researchView === 'personalized'
                ? data.analysis?.personalized_interpretation?.presentation
                : null
            }
            onEdit={openOnboarding}
          />
          <EvidenceAuditPanel audit={data.audit} />
          <ResearchWorkspace
            customerId={customerId}
            data={data}
            onAnalyze={analyze}
            onRequireProfile={openOnboarding}
          />
          <ReportSections
            data={data}
            historyLoading={historyLoading}
            onPeriodChange={changePeriod}
            onValuationChange={updateValuation}
            researchView={researchView}
          />
        </main>
      )}

      {!loading && compare && (
        <main className="results">
          <div className="report-heading">
            <div>
              <p className="eyebrow">{t('peerKicker')}</p>
              <h1>{t('compareTitle')} <em>{t('compareTitleEm')}</em></h1>
            </div>
          </div>
          <EvidenceAuditPanel audit={compareAudit} />
          <CompareTable data={compare} />
        </main>
      )}

      {!loading && !data && !compare && !error && <EmptyState onAnalyze={analyze} />}

      <footer className="site-footer">
        <div><span className="brand-mini">FS</span> {t('footerTagline')}</div>
        <p>{t('footerDisclaimer')}</p>
      </footer>
      <CustomerOnboarding />
      <AssistantWidget customerId={customerId} currentReport={assistantReport} />
    </div>
  )
}
