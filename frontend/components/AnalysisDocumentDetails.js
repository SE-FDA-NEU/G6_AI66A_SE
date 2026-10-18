import { useI18n } from '../lib/i18n';
import DocumentMetadata from './DocumentMetadata';

const warnings = {
  analysis_not_configured: 'Chưa cấu hình Gemini. Thêm GEMINI_API_KEY vào backend/.env rồi tải lại tài liệu để phân tích.',
  no_text_layer: 'Tài liệu không có lớp chữ để phân tích. Hệ thống không tự tạo nội dung hoặc chạy OCR.',
  source_truncated: 'Đã chọn các đoạn nguồn trong giới hạn tiết kiệm token. Kết quả chưa bao quát toàn bộ tài liệu.',
  unverified_claims: 'Một số nội dung chưa có bằng chứng nguồn hợp lệ.',
  insufficient_concepts: 'Tài liệu nguồn không đủ để hỗ trợ tổng quan 3-5 khái niệm cốt lõi. Không tự tạo khái niệm khi thiếu căn cứ nguồn.',
  insufficient_actions: 'Tài liệu không đủ căn cứ nguồn để hỗ trợ hai hành động đề xuất.',
};

export default function AnalysisDocumentDetails({ document }) {
  const { t, locale, errorText } = useI18n();
  return <>
    {document.label && (document.label.ai_label || document.label.user_label || document.label.ai_confidence != null) &&
      <DocumentMetadata document={document} showFolder={false} className="analysis-label" />}
    {document.warnings?.filter(warning => !(warning === 'insufficient_actions' &&
      document.analysis_status === 'completed' && document.output?.type === 'bullet')).map(warning => <p className="analysis-warning" key={warning}>
      {t(warnings[warning] || t("Có lưu ý khi xử lý tài liệu."))}
    </p>)}
    {document.error_message && <p className="analysis-error error-box" role="alert" data-testid="document-analysis-error">
      {errorText(document.error_message)}
    </p>}
    {document.analysis_status === 'failed' && !document.error_message && <p
      className="analysis-error error-box" role="alert" data-testid="document-analysis-failed">{t("Xử lý phân tích tài liệu thất bại.")}</p>}
    {document.analysis_status === 'completed' && document.analysis_metadata?.cache_hit &&
      <p className="analysis-note">{t("Đã dùng kết quả lưu sẵn, không gọi lại Gemini.")}</p>}
  </>;
}
