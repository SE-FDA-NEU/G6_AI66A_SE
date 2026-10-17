/**
 * CitationBadge and ClaimEvidence shared components.
 * 
 * BR05 & US08/US09:
 * - Valid evidence renders as: "Document name — page X" (or slide X)
 * - Unsupported claims render as "Unverified" without a fake anchor link
 * - Citation links carry document ID, page, evidence ID, and optional return job ID
 * - Multiple sources render as separate, distinct badges
 */

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

export function formatCitationText(source, documentName, currentDocumentId, pageKind = 'page') {
  let docId = currentDocumentId;
  let kind = pageKind;
  if (typeof currentDocumentId === 'string' && (currentDocumentId === 'page' || currentDocumentId === 'slide')) {
    kind = currentDocumentId;
    docId = undefined;
  }
  let docName = source.doc_name;
  if (!docName) {
    if (docId && source.document_id !== docId) {
      docName = `Document #${source.document_id}`;
    } else {
      docName = documentName || `Document #${source.document_id}`;
    }
  }
  const pageLabel = kind === 'slide' ? 'slide' : 'page';
  return `${docName} — ${pageLabel} ${source.page}`;
}

export function CitationBadge({ source, documentName, currentDocumentId, jobId, pageKind = 'page' }) {
  if (!source || !source.document_id) return null;
  const href = buildCitationHref(source, jobId);
  const text = formatCitationText(source, documentName, currentDocumentId, pageKind);

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
  return (
    <span className="unverified-badge analysis-unverified" role="status" aria-label="Khẳng định chưa được xác thực">
      {text}{note ? ` · ${note}` : ''}
    </span>
  );
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
  if (!claim) return null;
  const hasText = Boolean(claim.text);
  const hasEvidence = Array.isArray(claim.evidence) && claim.evidence.length > 0;
  const isUnverified = claim.unverified || !hasEvidence;

  if (!hasText) {
    return (
      <div className={`analysis-claim ${className}`}>
        <span className="analysis-unverified unverified-badge">Không có thông tin · Unverified</span>
      </div>
    );
  }

  return (
    <div className={`analysis-claim ${className}`}>
      <p className="claim-text">{claim.text}</p>
      <div className="claim-citations">
        {isUnverified && <UnverifiedBadge />}
        {showEvidence && hasEvidence && (
          <div className="evidence-badges">
            {claim.evidence.map((source, index) => (
              <CitationBadge
                key={index}
                source={source}
                documentName={documentName}
                currentDocumentId={documentId}
                jobId={jobId}
                pageKind={pageKind}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default CitationBadge;
