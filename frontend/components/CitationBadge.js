import { translate } from '../lib/i18n-core';
import { useI18n } from '../lib/i18n';
/**
 * CitationBadge and ClaimEvidence shared components.
 * 
 * BR05 & US08/US09:
 * - Valid evidence renders as: "Document name — page X" (or slide X)
 * - Unsupported claims render as "Unverified" without a fake anchor link
 * - Citation links carry document ID, page, evidence ID, and optional return job ID
 * - Multiple sources render as separate, distinct badges
 */

export function isUsableSource(source) {
  const quote = source?.quote ?? source?.snippet;
  return Boolean(source && Number.isSafeInteger(source.document_id) && source.document_id > 0 &&
    Number.isSafeInteger(source.page) && source.page > 0 &&
    Number.isSafeInteger(source.start) && source.start >= 0 &&
    Number.isSafeInteger(source.end) && source.end > source.start &&
    typeof quote === 'string' && quote.trim() &&
    typeof source.reader_version === 'string' && /^[0-9a-f]{64}$/.test(source.reader_version));
}

export function claimVerification(claim) {
  const hasText = typeof claim?.text === 'string' && Boolean(claim.text.trim());
  const evidence = Array.isArray(claim?.evidence) ? claim.evidence : [];
  const sources = hasText ? evidence.filter(isUsableSource) : [];
  return { hasText, sources, unverified: Boolean(claim?.unverified || !sources.length ||
    sources.length !== evidence.length || (Array.isArray(claim?.verification_issues) && claim.verification_issues.length)) };
}

export function buildEvidenceId(source) {
  if (source.evidence_id != null) return String(source.evidence_id);
  if (source.id != null) return String(source.id);
  const start = source.start ?? 0;
  const end = source.end ?? 0;
  return `${source.document_id}-${source.page}-${start}-${end}`;
}

export function buildCitationHref(source, jobId) {
  const params = new URLSearchParams();
  if (source.page != null) params.set('page', String(source.page));
  if (source.start != null) params.set('start', String(source.start));
  if (source.end != null) params.set('end', String(source.end));
  params.set('evidence', buildEvidenceId(source));
  if (jobId != null) params.set('job', String(jobId));
  return `/documents/${source.document_id}?${params.toString()}`;
}

export function formatCitationText(source, documentName, currentDocumentId, pageKind = 'page', locale = 'en') {
  let docId = currentDocumentId;
  let kind = pageKind;
  if (typeof currentDocumentId === 'string' && (currentDocumentId === 'page' || currentDocumentId === 'slide')) {
    kind = currentDocumentId;
    docId = undefined;
  }
  let docName = source.doc_name;
  if (!docName) {
    if (docId && source.document_id !== docId) {
      docName = translate(locale, 'Document #{0}', source.document_id);
    } else {
      docName = documentName || translate(locale, 'Document #{0}', source.document_id);
    }
  }
  const pageLabel = translate(locale, kind === 'slide' ? 'slide' : 'page');
  return `${docName} — ${pageLabel} ${source.page}`;
}

export function CitationBadge({ source, documentName, currentDocumentId, jobId, pageKind = 'page' }) {
  const { locale } = useI18n();
  if (!isUsableSource(source)) return <UnverifiedBadge />;
  const href = buildCitationHref(source, jobId);
  const text = formatCitationText(source, documentName, currentDocumentId, pageKind, locale);

  return (
    <a
      className="citation-badge analysis-source"
      href={href}
      title={source.quote || text}
      data-document-id={source.document_id}
      data-page={source.page}
      data-evidence-id={buildEvidenceId(source)}
    >
      {text}
    </a>
  );
}

export function UnverifiedBadge({ text = 'Unverified', note = 'Cần kiểm tra' }) {
  const { t, locale, errorText } = useI18n();
  return (
    <span className="unverified-badge analysis-unverified" role="status" aria-label={t("Khẳng định chưa được xác thực")}>
      {t(text)}{note ? ` · ${t(note)}` : ''}
    </span>
  );
}

export function ClaimSources({ claim, documentName, documentId, jobId, pageKind = 'page', missingNote }) {
  const { t, locale, errorText } = useI18n();
  const { sources, unverified } = claimVerification(claim);
  return <div className="claim-citations">
    {unverified && <UnverifiedBadge note={!sources.length && missingNote ? missingNote : t("Cần kiểm tra")} />}
    {sources.length > 0 && <div className="evidence-badges">
      {sources.map((source, index) => <CitationBadge key={index} source={source} documentName={documentName}
        currentDocumentId={documentId} jobId={jobId} pageKind={pageKind} />)}
    </div>}
  </div>;
}

export function ClaimEvidence({
  claim,
  documentName,
  documentId,
  jobId,
  pageKind = 'page',
  className = '',
  showEvidence = true,
}) {
  const { t, locale, errorText } = useI18n();
  const { hasText, unverified } = claimVerification(claim);

  if (!hasText) {
    return (
      <div className={`analysis-claim ${className}`}>
        <UnverifiedBadge text={t("Không có thông tin · Unverified")} note="" />
      </div>
    );
  }

  return (
    <div className={`analysis-claim ${className}`}>
      <p className="claim-text">{claim.text}</p>
      {showEvidence ? <ClaimSources claim={claim} documentName={documentName} documentId={documentId}
        jobId={jobId} pageKind={pageKind} /> : unverified && <UnverifiedBadge />}
    </div>
  );
}

export default CitationBadge;
