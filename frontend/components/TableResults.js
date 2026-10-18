import { useI18n } from '../lib/i18n';
import { ClaimSources, ClaimEvidence, UnverifiedBadge } from './CitationBadge';
import AnalysisDocumentDetails from './AnalysisDocumentDetails';

const TABLE_FIELDS = [
  ['value', 'Giá trị'],
  ['payment_term', 'Thanh toán'],
  ['penalty', 'Phạt'],
];

const fileStates = {
  pending: 'Đang chờ xử lý',
  processing: 'Đang phân tích',
  timed_out: 'Đã hết thời gian xử lý · Unverified',
  failed: 'Phân tích thất bại · Unverified',
};

export function TableResults({ documents = [], jobFiles = [], jobId }) {
  const { t, locale, errorText } = useI18n();
  const results = new Map(documents.map(document => [document.document_id, document]));
  // The existing job owns row identity and order, including files without a result yet.
  const rows = jobFiles.length ? jobFiles : documents;
  if (!rows.length) return null;

  return (
    <div className="analysis-card analysis-table-wrap" role="region" tabIndex={0} aria-label={t("Bảng điều khoản hợp đồng")}>
      <table className="financial-comparison-table">
        <caption>{t("So sánh điều khoản tài chính")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("Tài liệu")}</th>
            {TABLE_FIELDS.map(([field, label]) => <th key={field} scope="col">{t(label)}</th>)}
            <th scope="col">{t("Nguồn")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(file => {
            const document = results.get(file.document_id);
            const hasResult = document?.analysis_status === 'completed' &&
              (!file.status || file.status === 'completed');
            const name = file.original_filename || document?.original_filename || t("Tài liệu #{0}", file.document_id);
            return <tr key={file.document_id} data-document-id={file.document_id}>
              <th scope="row">
                <a className="analysis-source" href={`/documents/${file.document_id}?page=1`}>{name}</a>
                {document && <AnalysisDocumentDetails document={document} />}
              </th>
              {hasResult ? <>{TABLE_FIELDS.map(([field, label]) => <td key={field} className={`table-field-${field}`}>
                <span className="financial-field-label" aria-hidden="true">{t(label)}</span>
                <ClaimEvidence
                  claim={document.output[field] || { text: null, evidence: [], unverified: true }}
                  documentName={name}
                  documentId={file.document_id}
                  jobId={jobId}
                  pageKind={document.reader?.page_kind}
                  showEvidence={false}
                />
                {document.output[field]?.verification_issues?.includes('unsupported_fact') &&
                  <p className="analysis-unverified">{t("Nguồn không hỗ trợ nội dung này.")}</p>}
              </td>)}<td className="table-sources">
                <span className="financial-field-label" aria-hidden="true">{t("Nguồn")}</span>
                {TABLE_FIELDS.map(([field, label]) => {
                  const claim = document.output[field];
                  return <div key={field} className={`table-source-${field}`} role="group" aria-label={t("Nguồn: {0}", t(label))}>
                    <p className="financial-source-label">{t(label)}</p>
                    <ClaimSources
                      claim={claim}
                      documentName={name}
                      documentId={file.document_id}
                      jobId={jobId}
                      pageKind={document.reader?.page_kind}
                      missingNote={t("Chưa có nguồn xác thực")}
                    />
                  </div>;
                })}
              </td></> : <td colSpan={4}>
                <p className="analysis-unverified">{['pending', 'processing'].includes(file.status) ? t(fileStates[file.status]) :
                  <UnverifiedBadge text={t(fileStates[file.status]) || t("Chưa có kết quả phân tích · Unverified")} note="" />}</p>
              </td>}
            </tr>;
          })}
        </tbody>
      </table>
    </div>
  );
}

export default TableResults;
