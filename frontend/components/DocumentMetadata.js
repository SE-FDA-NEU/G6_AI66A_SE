import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
/**
 * Reusable Document Metadata UI (US10 / BR06 / BR07)
 * Displays AI classification label, confidence score, Needs review state,
 * and folder placement.
 *
 * NOTE:
 * - AI confidence represents document-level classifier probability and is kept
 *   strictly distinct from factual claim verification (CitationBadge / UnverifiedBadge).
 * - DocumentLabelEditor provides the shared human confirmation/edit controls.
 * - Scores >= 80% represent high-confidence AI suggestions; scores < 80% display "Needs review".
 */
export function DocumentMetadata({
  aiLabel,
  aiConfidence,
  reviewState,
  userLabel,
  folderId,
  folderName,
  showFolder = true,
  document,
  className = '',
}) {
  const { t, locale, errorText } = useI18n();
  const label = aiLabel !== undefined ? aiLabel : (document?.ai_label ?? document?.label?.ai_label);
  const confidence = aiConfidence !== undefined
    ? aiConfidence
    : (document?.ai_confidence !== undefined ? document.ai_confidence : document?.label?.ai_confidence);
  const rawState = reviewState !== undefined
    ? reviewState
    : (document?.review_state ?? document?.label?.review_state ?? 'needs_review');
  const state = typeof rawState === 'string' ? rawState : (rawState?.value || 'needs_review');
  const userLab = userLabel !== undefined ? userLabel : (document?.user_label ?? document?.label?.user_label);
  const folder = folderId !== undefined
    ? folderId
    : (document?.folder_id !== undefined ? document.folder_id : null);

  // Confidence calculations & boundary threshold (80%)
  const percent = confidence != null && !isNaN(confidence) ? Number((Number(confidence) * 100).toFixed(2)) : null;
  const isHighConfidence = percent != null ? Number(confidence) >= .8 : false;
  const isLowConfidence = percent != null ? Number(confidence) < .8 : false;

  const isConfirmed = state === 'confirmed';

  return (
    <div
      className={ui(`document-metadata ${className}`.trim())}
      data-testid="document-metadata"
      aria-label={t("Thông tin phân loại tài liệu (AI Metadata)")}
    >
      {/* AI Label */}
      {label ? (
        <span className={ui('metadata-badge metadata-ai-label')} data-testid="document-ai-label" data-original-label={label || ''}>
          <span className={ui('metadata-badge-prefix')}>{t("Nhãn AI:")}</span>{' '}
          <strong>{label}</strong>
        </span>
      ) : (
        <span className={ui('metadata-badge metadata-ai-label metadata-empty')} data-testid="document-ai-label" data-original-label={label || ''}>{t("Chưa có nhãn AI")}</span>
      )}

      {/* AI Confidence (Distinct from factual verification) */}
      {percent != null && (
        <span
          className={ui(`metadata-badge metadata-confidence ${isHighConfidence ? 'confidence-high' : 'confidence-low'}`)}
          data-testid="document-ai-confidence"
          data-confidence-percent={percent}
          data-confidence-level={isHighConfidence ? 'high' : 'low'}
        >
          <span className={ui('metadata-badge-prefix')}>{t("Độ tin cậy:")}</span>{' '}
          <strong>{percent}%</strong>
        </span>
      )}

      {/* Needs review state / Status (80% boundary logic) */}
      {isConfirmed ? (
        <span
          className={ui('metadata-badge metadata-review-state review-confirmed')}
          data-testid="document-review-state"
          data-state="confirmed"
        >{t("Đã xác nhận")}</span>
      ) : isLowConfidence ? (
        <span
          className={ui('metadata-badge metadata-review-state review-needs-review')}
          data-testid="document-review-state"
          data-state="needs_review"
        >{t("Needs review · Cần kiểm tra")}</span>
      ) : (
        <span
          className={ui('metadata-badge metadata-review-state review-suggestion')}
          data-testid="document-review-state"
          data-state="needs_review"
        >
          {isHighConfidence ? t("Gợi ý độ tin cậy cao") : t("Nhãn AI · Chưa có điểm tin cậy")}
        </span>
      )}

      {/* Folder Placement (unchanged folder placement verification) */}
      {showFolder && <span
        className={ui('metadata-badge metadata-folder-placement')}
        data-testid="document-folder-placement"
        data-folder-id={folder != null ? folder : 'unassigned'}
      >
        <span className={ui('metadata-badge-prefix')}>{t("Thư mục:")}</span>{' '}
        {folderName ? (
          folderName
        ) : folder != null ? (
          `#${folder}`
        ) : (
          t("Chưa phân thư mục (Unassigned)")
        )}
      </span>}

      {/* User label if previously assigned */}
      {userLab && (
        <span className={ui('metadata-badge metadata-user-label')} data-testid="document-user-label">
          <span className={ui('metadata-badge-prefix')}>{t("Nhãn người dùng:")}</span>{' '}
          <strong>{userLab}</strong>
        </span>
      )}
      {userLab && <span className={ui('metadata-badge metadata-human-decision')} data-testid="document-user-decision">
        {isConfirmed ? (userLab === label ? t("Người dùng đã xác nhận gợi ý AI") : t("Người dùng đã chỉnh sửa và xác nhận")) : t("Bản nháp của người dùng · Chưa xác nhận")}
      </span>}
    </div>
  );
}

export default DocumentMetadata;
