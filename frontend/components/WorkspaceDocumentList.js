import { useEffect, useState } from 'react';
import DocumentMetadata from './DocumentMetadata';
import WorkspacePagination from './WorkspacePagination';
import DocumentFolderMove from './DocumentFolderMove';

const PAGE_SIZE = 10;

export default function WorkspaceDocumentList({ folderId = '', aiLabel = '', folders = [], foldersUnavailable = false, refreshKey = 0, onMoved }) {
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
        if (folderId) params.set('folder_id', folderId);
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
        if (!controller.signal.aborted) setError('Không thể tải danh sách tài liệu. Vui lòng thử lại.');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [page, attempt, folderId, aiLabel, refreshKey]);

  return (
    <section className="workspace-documents" aria-label="Danh sách tài liệu" aria-busy={loading}>
      <h2>Tài liệu của bạn</h2>
      {loading && <p role="status" className="muted">Đang tải danh sách tài liệu…</p>}
      {error && <div role="alert"><p className="error-box">{error}</p>
        <button className="btn" onClick={() => setAttempt(value => value + 1)}>Thử lại danh sách</button></div>}
      {!loading && !error && <>
        {documents.length === 0 ? <p className="muted">{page === 0
          ? (aiLabel ? (folderId ? 'Không có tài liệu khớp đồng thời thư mục và nhãn AI đã chọn.' : 'Không có tài liệu khớp nhãn AI đã chọn.')
            : folderId ? 'Thư mục này chưa có tài liệu.' : 'Chưa có tài liệu nào trong không gian làm việc. Tải tài liệu để bắt đầu.')
          : 'Không còn tài liệu trên trang này. Hãy quay về trang trước.'}</p> : (
          <ul className="workspace-document-list" aria-label="Danh sách tài liệu workspace">
            {documents.map(doc => <li key={doc.id} className="workspace-document-row"
              data-testid="workspace-document-row" data-document-id={doc.id}>
              <div className="document-row-main">
                <a href={`/documents/${doc.id}?page=1`} className="document-row-title"><strong>{doc.original_filename}</strong></a>
                <DocumentMetadata document={doc} folderName={folders.find(folder => folder.id === doc.folder_id)?.name} className="workspace-metadata-row" />
              </div>
              <DocumentFolderMove document={doc} folders={folders} foldersUnavailable={foldersUnavailable} onMoved={onMoved} />
            </li>)}
          </ul>
        )}
      </>}
      {(page > 0 || hasNext) && <WorkspacePagination label="Phân trang tài liệu" page={page}
        hasNext={hasNext && !error} busy={loading} onPage={setPage} />}
    </section>
  );
}
