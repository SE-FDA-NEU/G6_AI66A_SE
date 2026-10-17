import { ClaimEvidence } from './CitationBadge';

const TABLE_FIELDS = [
  ['value', 'Giá trị'],
  ['payment_term', 'Thanh toán'],
  ['penalty', 'Phạt'],
];

export function TableResults({ table, documentName, documentId, jobId, pageKind }) {
  if (!table) return null;

  return (
    <div className="analysis-table-wrap" aria-label="Bảng điều khoản hợp đồng">
      <table>
        <caption>Điều khoản hợp đồng</caption>
        <thead>
          <tr>
            <th scope="col">Nội dung</th>
            <th scope="col">Kết quả và nguồn</th>
          </tr>
        </thead>
        <tbody>
          {TABLE_FIELDS.map(([field, label]) => (
            <tr key={field} className={`table-row-${field}`}>
              <th scope="row">{label}</th>
              <td>
                <ClaimEvidence
                  claim={table[field]}
                  documentName={documentName}
                  documentId={documentId}
                  jobId={jobId}
                  pageKind={pageKind}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default TableResults;
