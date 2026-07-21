import { useTranslation } from '../hooks/useTranslation.js'
import { auditCheckedText, auditCheckRows, auditStatusKey } from '../lib/evidenceAudit.js'


const CHECK_LABELS = {
  unsupported_claim: 'auditUnsupportedClaims',
  stale_evidence: 'auditStaleEvidence',
  missing_citation: 'auditMissingCitations',
  conflicting_sources: 'auditConflictingSources',
  incorrect_unit: 'auditIncorrectUnits',
  inconsistent_number: 'auditInconsistentNumbers',
}

const CHECK_DETAILS = {
  unsupported_claim: 'auditUnsupportedDetail',
  stale_evidence: 'auditStaleDetail',
  missing_citation: 'auditMissingDetail',
  conflicting_sources: 'auditConflictingDetail',
  incorrect_unit: 'auditUnitDetail',
  inconsistent_number: 'auditNumberDetail',
}


export default function EvidenceAuditPanel({ audit }) {
  const { t } = useTranslation()
  if (!audit) return null
  const rows = auditCheckRows(audit)
  const issueTotal = rows.reduce((total, row) => total + row.count, 0)
  const statusKey = auditStatusKey(audit.status)

  return (
    <section className={`audit-card audit-${audit.status}`} aria-labelledby="evidence-audit-title">
      <div className="audit-heading">
        <div>
          <p className="section-kicker">{t('auditKicker')}</p>
          <h2 id="evidence-audit-title">{t('auditTitle')}</h2>
          <p>{t({
            passed: 'auditSummaryPassed',
            warning: 'auditSummaryWarning',
            blocked: 'auditSummaryBlocked',
          }[audit.status] || 'auditSummaryWarning')}</p>
        </div>
        <span className={`audit-status audit-status-${audit.status}`}>
          {t(statusKey)}
        </span>
      </div>

      <div className="audit-checks" aria-label={t('auditChecksLabel')}>
        {rows.map((row) => (
          <div className={row.count ? 'has-issues' : ''} key={row.code}>
            <span aria-hidden="true">{row.count ? '!' : '✓'}</span>
            <p>
              <strong>{t(CHECK_LABELS[row.code])}</strong>
              <small>{row.count ? `${row.count} ${t('auditIssues')}` : t('auditClear')}</small>
            </p>
          </div>
        ))}
      </div>

      <div className="audit-footnote">
        <span>{auditCheckedText(t('auditChecked'), audit)}</span>
        {audit.blocked_statements > 0 && (
          <strong>
            {t('auditBlockedCount').replace('{count}', audit.blocked_statements)}
          </strong>
        )}
      </div>

      {issueTotal > 0 && (
        <details className="audit-details">
          <summary>{t('auditReviewIssues')}</summary>
          <ol>
            {audit.issues.slice(0, 8).map((issue, index) => (
              <li key={`${issue.code}-${issue.path}-${index}`}>
                <span>{t(CHECK_LABELS[issue.code])}</span>
                <div>
                  <strong>{issue.section}</strong>
                  <code>{issue.path}</code>
                  <p>{t(CHECK_DETAILS[issue.code])}</p>
                </div>
              </li>
            ))}
          </ol>
          {audit.issues.length > 8 && (
            <p>{t('auditMoreIssues').replace('{count}', audit.issues.length - 8)}</p>
          )}
        </details>
      )}
    </section>
  )
}
