import { ClaimEvidence } from './CitationBadge';

export function BulletResults({ bullets, documentName, documentId, jobId, pageKind }) {
  if (!bullets || bullets.length === 0) return null;

  return (
    <section className="analysis-section analysis-bullets" aria-label="Tóm tắt điểm chính">
      <h4>Tóm tắt</h4>
      <ul className="bullets-list">
        {bullets.map((claim, index) => (
          <li key={index} className="bullet-item">
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

export default BulletResults;
