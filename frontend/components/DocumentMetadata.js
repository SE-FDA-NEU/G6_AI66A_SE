/**
 * Reusable Document Metadata UI (US10 / BR06 / BR07)
 * Displays AI classification label, confidence score, Needs review state,
 * and folder placement.
 *
 * NOTE:
 * - AI confidence represents document-level classifier probability and is kept
 *   strictly distinct from factual claim verification (CitationBadge / UnverifiedBadge).
 * - Confirmation and edit controls are implemented under US12 and are not duplicated here.
 * - Scores >= 80% represent high-confidence AI suggestions; scores < 80% display "Needs review".
 */
export function DocumentMetadata({
  aiLabel,
  aiConfidence,
  reviewState,
  userLabel,
  folderId,
  folderName,
  document,
  className = '',
}) {
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
  const percent = confidence != null && !isNaN(confidence) ? Math.round(Number(confidence) * 100) : null;
  const isHighConfidence = percent != null ? percent >= 80 : false;
  const isLowConfidence = percent != null ? percent < 80 : false;

  const isConfirmed = state === 'confirmed';

  return (
    <div
      className={`document-metadata ${className}`.trim()}
      data-testid="document-metadata"
      aria-label="Thông tin phân loại tài liệu (AI Metadata)"
    >
      {/* AI Label */}
      {label ? (
        <span className="metadata-badge metadata-ai-label" data-testid="document-ai-label">
          <span className="metadata-badge-prefix">Nhãn AI:</span>{' '}
          <strong>{label}</strong>
        </span>
      ) : (
        <span className="metadata-badge metadata-ai-label metadata-empty" data-testid="document-ai-label">
          Chưa có nhãn AI
        </span>
      )}

      {/* AI Confidence (Distinct from factual verification) */}
      {percent != null && (
        <span
          className={`metadata-badge metadata-confidence ${isHighConfidence ? 'confidence-high' : 'confidence-low'}`}
          data-testid="document-ai-confidence"
          data-confidence-percent={percent}
          data-confidence-level={isHighConfidence ? 'high' : 'low'}
        >
          <span className="metadata-badge-prefix">Độ tin cậy:</span>{' '}
          <strong>{percent}%</strong>
        </span>
      )}

      {/* Needs review state / Status (80% boundary logic) */}
      {isConfirmed ? (
        <span
          className="metadata-badge metadata-review-state review-confirmed"
          data-testid="document-review-state"
          data-state="confirmed"
        >
          Đã xác nhận
        </span>
      ) : isLowConfidence ? (
        <span
          className="metadata-badge metadata-review-state review-needs-review"
          data-testid="document-review-state"
          data-state="needs_review"
        >
          Needs review · Cần kiểm tra
        </span>
      ) : (
        <span
          className="metadata-badge metadata-review-state review-suggestion"
          data-testid="document-review-state"
          data-state="needs_review"
        >
          Gợi ý độ tin cậy cao
        </span>
      )}

      {/* Folder Placement (unchanged folder placement verification) */}
      <span
        className="metadata-badge metadata-folder-placement"
        data-testid="document-folder-placement"
        data-folder-id={folder != null ? folder : 'unassigned'}
      >
        <span className="metadata-badge-prefix">Thư mục:</span>{' '}
        {folderName ? (
          folderName
        ) : folder != null ? (
          `#${folder}`
        ) : (
          'Chưa phân thư mục (Unassigned)'
        )}
      </span>

      {/* User label if previously assigned */}
      {userLab && (
        <span className="metadata-badge metadata-user-label" data-testid="document-user-label">
          <span className="metadata-badge-prefix">Nhãn người dùng:</span>{' '}
          <strong>{userLab}</strong>
        </span>
      )}
    </div>
  );
}

export default DocumentMetadata;
