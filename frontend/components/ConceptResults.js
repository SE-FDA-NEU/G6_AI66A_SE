import { ClaimEvidence } from './CitationBadge';

export function ConceptResults({ concepts, documentName, documentId, jobId, pageKind }) {
  if (!concepts || concepts.length === 0) return null;

  return (
    <section className="analysis-section analysis-concepts" aria-label="Khái niệm chính">
      <h4>Khái niệm chính</h4>
      <div className="concepts-list">
        {concepts.map((concept, index) => (
          <article key={index} className="concept-card">
            <h5>{concept.name}</h5>
            <ClaimEvidence
              claim={concept.description}
              documentName={documentName}
              documentId={documentId}
              jobId={jobId}
              pageKind={pageKind}
            />
          </article>
        ))}
      </div>
    </section>
  );
}

export default ConceptResults;
