import { useEffect, useState } from 'react';
import { CitationBadge } from './CitationBadge';
import DocumentMetadata from './DocumentMetadata';
import WorkspacePagination from './WorkspacePagination';

const PAGE_SIZE = 10;

export function WorkspaceSearch({ jobId }) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('content');
  const [label, setLabel] = useState('');
  const [folder, setFolder] = useState('');
  const [request, setRequest] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    if (!request) { setResult(null); setError(''); setLoading(false); return; }
    async function search() {
      let failureMessage = 'Không thể tìm kiếm lúc này. Vui lòng thử lại.';
      setLoading(true);
      setError('');
      setResult(null);
      try {
        const params = new URLSearchParams({ q: request.query, mode: request.mode,
          limit: String(PAGE_SIZE), offset: String(request.page * PAGE_SIZE) });
        if (request.label) params.set('label', request.label);
        if (request.folder) params.set('folder_id', request.folder);
        const response = await fetch(`/api/search?${params}`, { signal: controller.signal, cache: 'no-store' });
        if (response.status === 401) { window.location.assign('/'); return; }
        if (!response.ok) {
          if (response.status === 422) failureMessage = 'Nhập từ khóa có chữ hoặc số và kiểm tra bộ lọc.';
          throw new Error();
        }
        const data = await response.json();
        if (!Array.isArray(data.hits) || !Number.isSafeInteger(data.total_hits) || data.total_hits < 0) throw new Error();
        if (!controller.signal.aborted) setResult(data);
      } catch {
        if (!controller.signal.aborted) setError(failureMessage);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    search();
    return () => controller.abort();
  }, [request]);

  function handleSearch(event) {
    event.preventDefault();
    if (!query.trim()) return;
    setResult(null);
    setRequest({ query: query.trim(), mode, label: label.trim(), folder, page: 0 });
  }

  function clearSearch() {
    setRequest(null);
    setResult(null); setError(''); setLoading(false);
    setQuery(''); setLabel(''); setFolder(''); setMode('content');
  }

  return (
    <section className="workspace-search" aria-label="Tìm kiếm tài liệu">
      <form className="search-form" onSubmit={handleSearch} role="search">
        <label htmlFor="workspace-search-input" className="search-label">Tìm kiếm trong tài liệu</label>
        <p className="search-help" id="workspace-search-help">Tìm trong toàn bộ tài liệu đã lập chỉ mục, kể cả tài liệu ngoài trang danh sách hiện tại.</p>
        <div className="search-bar">
          <input id="workspace-search-input" type="search" maxLength={500}
            placeholder="Nhập từ khóa, ví dụ: thanh toán, tiền phạt…" aria-describedby="workspace-search-help"
            value={query} onChange={event => setQuery(event.target.value)} />
          <button type="submit" className="btn primary" disabled={loading || !query.trim()}>
            {loading ? 'Đang tìm…' : 'Tìm kiếm'}
          </button>
          <button type="button" className="btn" onClick={clearSearch} disabled={!request && !query && !label && !folder}>Xóa tìm kiếm</button>
        </div>
        <div className="workspace-search-filters">
          <label>Kiểu tìm kiếm
            <select value={mode} onChange={event => setMode(event.target.value)}>
              <option value="content">Từ khóa</option><option value="semantic">Theo ý nghĩa</option>
            </select>
          </label>
          <label>Lọc theo nhãn<input value={label} maxLength={100} placeholder="Tất cả nhãn" onChange={event => setLabel(event.target.value)} /></label>
          <label>Thư mục (#)<input type="number" min="1" step="1" value={folder} placeholder="Tất cả thư mục" onChange={event => setFolder(event.target.value)} /></label>
        </div>
      </form>
      <div aria-live="polite" aria-busy={loading}>
        {loading && <p role="status">Đang tìm kiếm trong tài liệu…</p>}
        {error && <div role="alert"><p className="error-box">{error}</p>
          <button className="btn" onClick={() => setRequest({ ...request })}>Thử lại tìm kiếm</button></div>}
        {result && request && <div className="search-results">
          <p className="search-count">{result.total_hits > 0 ? `Tìm thấy ${result.total_hits} kết quả` : 'Không tìm thấy kết quả phù hợp'}{request && ` cho “${request.query}”`}</p>
          {result.total_hits > 0 && result.hits.length === 0 && <p>Không còn kết quả trên trang này. Hãy quay về trang trước.</p>}
          {result.hits.length > 0 && <>
            <p className="search-help">Đoạn trích được sắp xếp theo mức độ phù hợp. Mở nguồn để xem ngữ cảnh.</p>
            <ol className="search-hit-list" start={request.page * PAGE_SIZE + 1} aria-label="Danh sách kết quả tìm kiếm">
              {result.hits.map((hit, index) => <li key={`${hit.document_id}-${hit.page}-${hit.start}-${index}`} className="search-hit-card">
                <div className="search-hit-body">
                  <p className="search-hit-heading"><strong>{request.page * PAGE_SIZE + index + 1}. {hit.doc_name}</strong></p>
                  <p className="search-snippet">{hit.snippet}</p>
                  <DocumentMetadata aiLabel={hit.ai_label} folderId={hit.folder_id} className="search-hit-metadata" />
                  <div className="search-hit-citations"><CitationBadge source={hit} documentName={hit.doc_name} jobId={jobId} /></div>
                </div>
              </li>)}
            </ol>
          </>}
          {(result.total_hits > PAGE_SIZE || request.page > 0) && <WorkspacePagination label="Phân trang tìm kiếm"
            page={request.page} busy={loading} hasNext={(request.page + 1) * PAGE_SIZE < result.total_hits}
            onPage={page => setRequest({ ...request, page })} />}
        </div>}
      </div>
    </section>
  );
}

export default WorkspaceSearch;
