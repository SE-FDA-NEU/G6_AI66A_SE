import BulletResults from './BulletResults';
import ActionResults from './ActionResults';
import TableResults from './TableResults';
import ConceptResults from './ConceptResults';

const warnings = {
  analysis_not_configured: 'Chưa cấu hình Gemini. Thêm GEMINI_API_KEY vào backend/.env rồi tải lại tài liệu để phân tích.',
  no_text_layer: 'Tài liệu không có lớp chữ để phân tích. Hệ thống không tự tạo nội dung hoặc chạy OCR.',
  source_truncated: 'Đã chọn các đoạn nguồn trong giới hạn tiết kiệm token. Kết quả chưa bao quát toàn bộ tài liệu.',
  unverified_claims: 'Một số nội dung chưa có bằng chứng nguồn hợp lệ.',
  insufficient_concepts: 'Tài liệu nguồn không đủ để hỗ trợ tổng quan 3-5 khái niệm cốt lõi. Không tự tạo khái niệm khi thiếu căn cứ nguồn.',
};

export default function AnalysisResults({ data, jobId }) {
  const documents = Object.values(data?.documents || {}).filter(item => item?.schema_version === 1);
  if (!documents.length) return null;
  return <section className="analysis-results" aria-label="Kết quả phân tích AI">
    <h2>Kết quả phân tích</h2>
    {documents.map(document => <article className="analysis-card" key={document.document_id}>
      <h3>{document.original_filename}</h3>
      <a href={`/documents/${document.document_id}?page=1`}>Mở tài liệu nguồn</a>
      {document.label?.ai_label && <p className="analysis-label">
        Nhãn AI: <strong>{document.label.ai_label}</strong> · {Math.round(document.label.ai_confidence * 100)}%
        {document.label.confidence_level === 'low' && ' · Cần kiểm tra'}
        {document.label.user_label && <span> · Nhãn của bạn: {document.label.user_label}</span>}
      </p>}
      {document.warnings?.map(warning => <p className="analysis-warning" key={warning}>
        {warnings[warning] || warning}
      </p>)}
      {document.error_message && (
        <p className="analysis-error error-box" role="alert" data-testid="document-analysis-error">
          {document.error_message}
        </p>
      )}
      {document.analysis_status === 'failed' && !document.error_message && (
        <p className="analysis-error error-box" role="alert" data-testid="document-analysis-failed">
          Xử lý phân tích tài liệu thất bại.
        </p>
      )}
      {document.analysis_status === 'completed' && <>
        {document.output?.type === 'bullet' && <>
          <BulletResults
            bullets={document.output.bullets}
            documentName={document.original_filename}
            documentId={document.document_id}
            jobId={jobId}
            pageKind={document.reader?.page_kind}
          />
          <ActionResults
            actions={document.output.actions}
            documentName={document.original_filename}
            documentId={document.document_id}
            jobId={jobId}
            pageKind={document.reader?.page_kind}
          />
        </>}
        {document.output?.type === 'table' && <TableResults
          table={document.output}
          documentName={document.original_filename}
          documentId={document.document_id}
          jobId={jobId}
          pageKind={document.reader?.page_kind}
        />}
        {document.output?.type === 'concept' && <ConceptResults
          concepts={document.output.concepts}
          limitation={document.output.limitation}
          documentName={document.original_filename}
          documentId={document.document_id}
          jobId={jobId}
          pageKind={document.reader?.page_kind}
        />}
        {document.analysis_metadata?.cache_hit && <p className="analysis-note">Đã dùng kết quả lưu sẵn, không gọi lại Gemini.</p>}
      </>}
    </article>)}
  </section>;
}
