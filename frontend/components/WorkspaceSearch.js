import { useI18n } from '../lib/i18n';
import { useEffect, useState } from 'react';
import { CitationBadge } from './CitationBadge';
import DocumentMetadata from './DocumentMetadata';
import WorkspacePagination from './WorkspacePagination';

const PAGE_SIZE = 10;

export function WorkspaceSearch({ jobId, folders = [], foldersUnavailable = false, refreshKey = 0 }) {
  const { t, locale, errorText } = useI18n();
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
      let failureMessage = t("Không thể tìm kiếm lúc này. Vui lòng thử lại.");
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
          if (response.status === 503) {
            const failure = await response.json().catch(() => null);
            if (['embedding_rate_limited', 'embedding_unavailable'].includes(failure?.detail?.code) && typeof failure.detail.message === 'string') failureMessage = failure.detail.message;
          }
          if (response.status === 422) failureMessage = t("Nhập từ khóa có chữ hoặc số và kiểm tra bộ lọc.");
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
  }, [request, refreshKey]);

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
    <section className="workspace-search" aria-label={t("Tìm kiếm tài liệu")}>
      <form className="search-form" onSubmit={handleSearch} role="search">
        <label htmlFor="workspace-search-input" className="search-label">{t("Tìm kiếm trong tài liệu")}</label>
        <p className="search-help" id="workspace-search-help">{t("Bạn nhớ một câu hay ý trong tài liệu? Nhập từ khóa như “điều khoản thanh toán”. Kết quả là đoạn trích kèm trang nguồn, không phải tên tệp.")}</p>
        <div className="search-bar">
          <input id="workspace-search-input" type="search" maxLength={500}
            placeholder={t("Tìm nội dung, ví dụ: điều khoản thanh toán…")} aria-describedby="workspace-search-help"
            value={query} onChange={event => setQuery(event.target.value)} />
          <button type="submit" className="btn primary" disabled={loading || !query.trim()}>
            {loading ? t("Đang tìm…") : t("Tìm kiếm")}
          </button>
          <button type="button" className="btn" onClick={clearSearch} disabled={!request && !query && !label && !folder}>{t("Xóa tìm kiếm")}</button>
        </div>
        <div className="workspace-search-filters">
          <label>{t("Kiểu tìm kiếm")}<select value={mode} onChange={event => setMode(event.target.value)}>
              <option value="content">{t("Chứa từ khóa")}</option><option value="semantic">{t("Nội dung có ý nghĩa tương tự")}</option>
            </select>
          </label>
          <label>{t("Lọc theo nhãn")}<input value={label} maxLength={100} placeholder={t("Tất cả nhãn")} onChange={event => setLabel(event.target.value)} /></label>
          <div><label htmlFor="search-folder-select">{t("Thư mục tìm kiếm")}</label>
          <select id="search-folder-select" value={folder} disabled={foldersUnavailable} onChange={event => setFolder(event.target.value)}>
            <option value="">{t("Toàn bộ thư viện")}</option>
            {folders.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></div>
        </div>
      </form>
      <div aria-live="polite" aria-busy={loading}>
        {loading && <p role="status">{t("Đang tìm kiếm trong tài liệu…")}</p>}
        {loading && request?.mode === 'semantic' && <p className="search-help">{t("Lần đầu có thể lâu hơn vì cần lập chỉ mục nội dung. Những lần sau sẽ dùng lại chỉ mục đã lưu.")}</p>}
        {error && <div role="alert"><p className="error-box">{errorText(error)}</p>
          <button className="btn" onClick={() => setRequest({ ...request })}>{t("Thử lại tìm kiếm")}</button></div>}
        {result && request && <div className="search-results">
          <p className="search-help">{t("Phạm vi:") + " "}{request.folder ? folders.find(item => String(item.id) === request.folder)?.name || t("Thư mục đã chọn") : t("Toàn bộ thư viện")}{" " + t("· Nội dung tài liệu đã lập chỉ mục")}</p><p className="search-count">{result.total_hits > 0 ? t("Tìm thấy {0} kết quả", result.total_hits) : t("Không tìm thấy kết quả phù hợp")}{request && ` cho “${request.query}”`}</p>
          {result.total_hits > 0 && result.hits.length === 0 && <p>{t("Không còn kết quả trên trang này. Hãy quay về trang trước.")}</p>}
          {result.hits.length > 0 && <>
            <p className="search-help">{t("Đoạn trích được sắp xếp theo mức độ phù hợp. Mở nguồn để xem ngữ cảnh.")}</p>
            <ol className="search-hit-list" start={request.page * PAGE_SIZE + 1} aria-label={t("Danh sách kết quả tìm kiếm")}>
              {result.hits.map((hit, index) => <li key={`${hit.document_id}-${hit.page}-${hit.start}-${index}`} className="search-hit-card">
                <div className="search-hit-body">
                  <p className="search-hit-heading"><strong>{request.page * PAGE_SIZE + index + 1}. {hit.doc_name}</strong></p>
                  <p className="search-snippet">{hit.snippet}</p>
                  <DocumentMetadata aiLabel={hit.ai_label} folderId={hit.folder_id}
                    folderName={folders.find(item => item.id === hit.folder_id)?.name} className="search-hit-metadata" />
                  <div className="search-hit-citations"><CitationBadge source={hit} documentName={hit.doc_name} jobId={jobId} /></div>
                </div>
              </li>)}
            </ol>
          </>}
          {(result.total_hits > PAGE_SIZE || request.page > 0) && <WorkspacePagination label={t("Phân trang tìm kiếm")}
            page={request.page} busy={loading} hasNext={(request.page + 1) * PAGE_SIZE < result.total_hits}
            onPage={page => setRequest({ ...request, page })} />}
        </div>}
      </div>
    </section>
  );
}

export default WorkspaceSearch;
