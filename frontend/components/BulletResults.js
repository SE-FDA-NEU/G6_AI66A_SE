import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { ClaimEvidence } from './CitationBadge';

export function BulletResults({ bullets, documentName, documentId, jobId, pageKind }) {
  const { t, locale, errorText } = useI18n();
  if (!bullets || bullets.length === 0) return null;

  return (
    <section className={ui('analysis-section analysis-bullets')} aria-label={t("Tóm tắt điểm chính")}>
      <h4>{t("Tóm tắt")}</h4>
      <ul className={ui('bullets-list')}>
        {bullets.map((claim, index) => (
          <li key={index} className={ui('bullet-item')}>
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
