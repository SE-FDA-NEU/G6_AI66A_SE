import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { ClaimEvidence } from './CitationBadge';

export function ConceptResults({ concepts, limitation, documentName, documentId, jobId, pageKind }) {
  const { t, locale, errorText } = useI18n();
  const hasConcepts = Array.isArray(concepts) && concepts.length > 0;

  return (
    <section className={ui('analysis-section analysis-concepts')} aria-label={t("Khái niệm chính")}>
      <h4>{t("Khái niệm chính")}</h4>
      {limitation ? (
        <div className={ui('concept-limitation')} data-testid="concept-limitation">
          <p>{limitation}</p>
        </div>
      ) : !hasConcepts ? (
        <div className={ui('concept-limitation concept-empty-state')} data-testid="concept-limitation">
          <p>{t("Tài liệu không có đủ nội dung để rút ra các khái niệm chính.")}</p>
        </div>
      ) : null}
      {hasConcepts && (
        <div className={ui('concepts-list')}>
          {concepts.map((concept, index) => (
            <article key={index} className={ui('concept-card')} data-testid={`concept-card-${index}`}>
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
