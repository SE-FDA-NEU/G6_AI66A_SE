import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import BulletResults from './BulletResults';
import ActionResults from './ActionResults';
import TableResults from './TableResults';
import ConceptResults from './ConceptResults';
import AnalysisDocumentDetails from './AnalysisDocumentDetails';

export default function AnalysisResults({ data, jobId, mode, jobFiles = [], title = 'Kết quả phân tích' }) {
  const { t, locale, errorText } = useI18n();
  const documents = Object.values(data?.documents || {}).filter(item => item?.schema_version === 1);
  const tableDocuments = documents.filter(document => document.output?.type === 'table');
  const showTable = mode === 'table' || tableDocuments.length > 0;
  if (!documents.length && !showTable) return null;
  return <section id={title ? 'analysis-output' : undefined} className={ui('analysis-results')} aria-label={t("Kết quả phân tích AI")}>
    {title && <p className="font-mono text-[10px] tracking-widest text-zinc-500">04 // ANALYSIS_OUTPUT</p>}
    {title && <h2>{t(title)}</h2>}
    {showTable && <TableResults documents={tableDocuments} jobId={jobId} jobFiles={jobFiles} />}
    {documents.filter(document => document.output?.type !== 'table').map(document => <article className={ui('analysis-card')} key={document.document_id}>
      <h3>{document.original_filename}</h3>
      <a href={`/documents/${document.document_id}?page=1`}>{t("Mở tài liệu nguồn")}</a>
      <AnalysisDocumentDetails document={document} />
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
            limitation={document.output.limitation}
            documentName={document.original_filename}
            documentId={document.document_id}
            jobId={jobId}
            pageKind={document.reader?.page_kind}
          />
        </>}
        {document.output?.type === 'concept' && <ConceptResults
          concepts={document.output.concepts}
          limitation={document.output.limitation}
          documentName={document.original_filename}
          documentId={document.document_id}
          jobId={jobId}
          pageKind={document.reader?.page_kind}
        />}
      </>}
    </article>)}
  </section>;
}
