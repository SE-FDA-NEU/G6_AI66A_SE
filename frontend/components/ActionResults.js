import { ClaimEvidence } from './CitationBadge';

export function ActionResults({ actions = [], limitation, documentName, documentId, jobId, pageKind }) {
  const recommendations = actions || [];
  // Older saved results may not have the explicit limitation field yet.
  const sourceLimitation = limitation || (recommendations.length < 2
    ? 'Tài liệu không đủ căn cứ nguồn để hỗ trợ hai hành động đề xuất.' : null);

  return (
    <section className="analysis-section analysis-actions" aria-label="Recommended actions">
      <h4>Recommended actions</h4>
      {sourceLimitation && <p className="analysis-warning" data-testid="action-limitation">{sourceLimitation}</p>}
      {recommendations.length > 0 && <ul className="actions-list">
        {recommendations.map((claim, index) => (
          <li key={index} className="action-item">
            <ClaimEvidence
              claim={claim}
              documentName={documentName}
              documentId={documentId}
              jobId={jobId}
              pageKind={pageKind}
            />
          </li>
        ))}
      </ul>}
    </section>
  );
}

export default ActionResults;
