import { ClaimEvidence } from './CitationBadge';

export function ConceptResults({ concepts, limitation, documentName, documentId, jobId, pageKind }) {
  const hasConcepts = Array.isArray(concepts) && concepts.length > 0;
  if (!hasConcepts && !limitation) return null;

  return (
    <section className="analysis-section analysis-concepts" aria-label="Khái niệm chính">
      <h4>Khái niệm chính</h4>
      {limitation && (
        <div className="concept-limitation" data-testid="concept-limitation">
          <p>{limitation}</p>
        </div>
      )}
      {hasConcepts && (
        <div className="concepts-list">
          {concepts.map((concept, index) => (
            <article key={index} className="concept-card" data-testid={`concept-card-${index}`}>
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
      )}
    </section>
  );
}

export default ConceptResults;
