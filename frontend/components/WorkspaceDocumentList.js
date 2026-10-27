import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { useEffect, useState } from 'react';
import DocumentMetadata from './DocumentMetadata';
import WorkspacePagination from './WorkspacePagination';
import DocumentFolderMove from './DocumentFolderMove';
import DocumentLabelEditor from './DocumentLabelEditor';
import DocumentExpiry from './DocumentExpiry';
import WorkspaceIcon from './WorkspaceIcon';

const PAGE_SIZE = 10;

export default function WorkspaceDocumentList({ folderId = '', aiLabel = '', folders = [], foldersUnavailable = false, refreshKey = 0, filename = '', onMoved, onLabelSaved }) {
  const { t, locale, errorText } = useI18n();
  const [page, setPage] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [documents, setDocuments] = useState([]);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError('');
      try {
        // The list API returns an array, so one extra row identifies a next page.
        const params = new URLSearchParams({ skip: String(page * PAGE_SIZE), limit: String(PAGE_SIZE + 1) });
        if (folderId === 'unassigned') params.set('unassigned', 'true');
        else if (folderId) params.set('folder_id', folderId);
        if (filename) params.set('filename', filename);
        if (aiLabel) params.set('label', aiLabel);
        const response = await fetch(`/api/documents?${params}`,
          { signal: controller.signal, cache: 'no-store' });
        if (response.status === 401) { window.location.assign('/'); return; }
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (!Array.isArray(data)) throw new Error();
        if (controller.signal.aborted) return;
        if (data.length === 0 && page > 0) { setPage(value => value - 1); return; }
        setDocuments(data.slice(0, PAGE_SIZE));
        setHasNext(data.length > PAGE_SIZE);
      } catch {
        if (!controller.signal.aborted) setError(t("Không thể tải danh sách tài liệu. Vui lòng thử lại."));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [page, attempt, folderId, aiLabel, refreshKey, filename]);

  return (
    <section className={ui('workspace-documents')} aria-label={t("Danh sách tài liệu")} aria-busy={loading}>
      <div className={ui('section-heading')}><h2>{t("Tài liệu của bạn")}</h2><span className={ui('view-caption')}><WorkspaceIcon name="grid" size={16}/>{" " + t("Dạng thẻ")}</span></div>
      {loading && <p role="status" className={ui('muted')}>{t("Đang tải danh sách tài liệu…")}</p>}
      {error && <div role="alert"><p className={ui('error-box')}>{errorText(error)}</p>
        <button className={ui('btn')} onClick={() => setAttempt(value => value + 1)}>{t("Thử lại danh sách")}</button></div>}
      {!loading && !error && <>
        {documents.length === 0 ? <p className={ui('muted')}>{page === 0
          ? (filename ? t("Không tìm thấy tệp có tên chứa “{0}”.", filename) : aiLabel ? (folderId ? t("Không có tài liệu khớp đồng thời thư mục và nhãn AI đã chọn.") : t("Không có tài liệu khớp nhãn AI đã chọn."))
            : folderId ? t("Thư mục này chưa có tài liệu.") : t("Chưa có tài liệu nào trong không gian làm việc. Tải tài liệu để bắt đầu."))
          : t("Không còn tài liệu trên trang này. Hãy quay về trang trước.")}</p> : (
          <ul className={ui('workspace-document-list')} aria-label={t("Danh sách tài liệu workspace")}>
            {documents.map((doc, index) => <li key={doc.id} className={ui('workspace-document-row')}
              data-testid="workspace-document-row" data-document-id={doc.id}>
              <p className="font-mono text-[10px] text-zinc-600">{String(page * PAGE_SIZE + index + 1).padStart(2, '0')} // DOCUMENT</p>
              <div className={ui('document-row-main')}>
                <a href={`/documents/${doc.id}?page=1`} className={ui('document-row-title')} aria-label={doc.original_filename}><span className={ui(`file-cover file-cover-${doc.original_filename.split('.').pop().toLowerCase()}`)}><WorkspaceIcon name="file" size={45}/><span>{doc.original_filename.split('.').pop().toUpperCase()}</span></span>
                <strong>{doc.original_filename}</strong></a>
                <DocumentMetadata document={doc} folderName={folders.find(folder => folder.id === doc.folder_id)?.name} className={ui('workspace-metadata-row')} />
                <DocumentExpiry expiresAt={doc.expires_at} />
              </div>
              <DocumentLabelEditor documentId={doc.id} document={doc} onSaved={onLabelSaved} />
              <DocumentFolderMove document={doc} folders={folders} foldersUnavailable={foldersUnavailable} onMoved={onMoved} />
            </li>)}
          </ul>
        )}
      </>}
      {(page > 0 || hasNext) && <WorkspacePagination label={t("Phân trang tài liệu")} page={page}
        hasNext={hasNext && !error} busy={loading} onPage={setPage} />}
    </section>
  );
}
