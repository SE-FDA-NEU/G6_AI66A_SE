import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { ClaimEvidence } from './CitationBadge';

export function ActionResults({ actions = [], limitation, documentName, documentId, jobId, pageKind }) {
  const { t, locale, errorText } = useI18n();
  const recommendations = actions || [];
  // Older saved results may not have the explicit limitation field yet.
  const sourceLimitation = limitation || (recommendations.length < 2
    ? t("Tài liệu không đủ căn cứ nguồn để hỗ trợ hai hành động đề xuất.") : null);

  return (
    <section className={ui('analysis-section analysis-actions')} aria-label={t("Recommended actions")}>
      <h4>{t("Recommended actions")}</h4>
      {sourceLimitation && <p className={ui('analysis-warning')} data-testid="action-limitation">{sourceLimitation}</p>}
      {recommendations.length > 0 && <ul className={ui('actions-list')}>
        {recommendations.map((claim, index) => (
          <li key={index} className={ui('action-item')}>
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
