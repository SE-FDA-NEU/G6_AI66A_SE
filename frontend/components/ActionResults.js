import { ClaimEvidence } from './CitationBadge';

export function ActionResults({ actions, documentName, documentId, jobId, pageKind }) {
  if (!actions || actions.length === 0) return null;

  return (
    <section className="analysis-section analysis-actions" aria-label="Hành động đề xuất">
      <h4>Hành động đề xuất</h4>
      <ul className="actions-list">
        {actions.map((claim, index) => (
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
      </ul>
    </section>
  );
}

export default ActionResults;
