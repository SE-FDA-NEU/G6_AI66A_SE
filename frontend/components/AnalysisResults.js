const warnings = {
  analysis_not_configured: 'Chưa cấu hình Gemini. Thêm GEMINI_API_KEY vào backend/.env rồi tải lại tài liệu để phân tích.',
  no_text_layer: 'Tài liệu không có lớp chữ để phân tích. Hệ thống không tự tạo nội dung hoặc chạy OCR.',
  source_truncated: 'Đã chọn các đoạn nguồn trong giới hạn tiết kiệm token. Kết quả chưa bao quát toàn bộ tài liệu.',
  unverified_claims: 'Một số nội dung chưa có bằng chứng nguồn hợp lệ.',
};

function Claim({ value, pageKind }) {
  if (!value?.text) return <span className="analysis-unverified">Không có thông tin · Unverified</span>;
  return <div className="analysis-claim">
    <p>{value.text}</p>
    {value.unverified && <span className="analysis-unverified">Unverified · Cần kiểm tra</span>}
    {value.evidence?.map((source, index) =>
      <a className="analysis-source" key={index}
        href={`/documents/${source.document_id}?page=${source.page}&start=${source.start}&end=${source.end}`} title={source.quote}>
        {pageKind === 'slide' ? 'Slide' : 'Trang'} {source.page} · #{source.document_id}
      </a>)}
  </div>;
}

export default function AnalysisResults({ data }) {
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
      {document.analysis_status === 'completed' && <>
        {document.output?.type === 'bullet' && <>
          <h4>Tóm tắt</h4>
          <ul>{document.output.bullets.map((claim, index) => <li key={index}>
            <Claim value={claim} pageKind={document.reader?.page_kind} /></li>)}</ul>
          {document.output.actions?.length > 0 && <><h4>Hành động đề xuất</h4>
            <ul>{document.output.actions.map((claim, index) => <li key={index}>
              <Claim value={claim} pageKind={document.reader?.page_kind} /></li>)}</ul></>}
        </>}
        {document.output?.type === 'table' && <div className="analysis-table-wrap"><table>
          <caption>Điều khoản hợp đồng</caption>
          <thead><tr><th scope="col">Nội dung</th><th scope="col">Kết quả và nguồn</th></tr></thead>
          <tbody>{[['value', 'Giá trị'], ['payment_term', 'Thanh toán'], ['penalty', 'Phạt']].map(([field, label]) =>
            <tr key={field}><th scope="row">{label}</th><td>
              <Claim value={document.output[field]} pageKind={document.reader?.page_kind} />
            </td></tr>)}</tbody>
        </table></div>}
        {document.output?.type === 'concept' && <><h4>Khái niệm chính</h4>
          {document.output.concepts.map((concept, index) => <section key={index}>
            <h5>{concept.name}</h5><Claim value={concept.description} pageKind={document.reader?.page_kind} />
          </section>)}</>}
        {document.analysis_metadata?.cache_hit && <p className="analysis-note">Đã dùng kết quả lưu sẵn, không gọi lại Gemini.</p>}
      </>}
    </article>)}
  </section>;
}
