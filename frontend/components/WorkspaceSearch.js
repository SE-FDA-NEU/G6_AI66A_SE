import { useState } from 'react';
import { CitationBadge } from './CitationBadge';

export function WorkspaceSearch({ initialHits = [], jobId }) {
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState(initialHits);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(initialHits.length > 0);
  const [error, setError] = useState('');

  async function handleSearch(e) {
    e?.preventDefault();
    const q = query.trim();
    if (!q) return;

    setLoading(true);
    setError('');
    try {
      const response = await fetch(`/api/documents?search=${encodeURIComponent(q)}`);
      if (response.status === 401) {
        window.location.assign('/');
        return;
      }
      if (!response.ok) throw new Error('Không thể tìm kiếm lúc này.');
      const docs = await response.json();

      // Transform matching documents into search hit source references
      const matchingHits = docs.map((doc) => ({
        document_id: doc.id,
        doc_name: doc.original_filename,
        page: 1,
        start: 0,
        end: Math.min(q.length, 50),
        quote: q,
        snippet: doc.ai_label ? `${doc.original_filename} · Nhãn: ${doc.ai_label}` : doc.original_filename,
        ai_label: doc.ai_label,
      }));

      setHits(matchingHits);
      setSearched(true);
    } catch (err) {
      setError(err.message || 'Lỗi khi tìm kiếm');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="workspace-search" aria-label="Tìm kiếm tài liệu">
      <form className="search-form" onSubmit={handleSearch} role="search">
        <label htmlFor="workspace-search-input" className="search-label">
          Tìm kiếm trong tài liệu
        </label>
        <div className="search-bar">
          <input
            id="workspace-search-input"
            type="search"
            placeholder="Nhập từ khóa tìm kiếm (ví dụ: hợp đồng, lãi suất, phạt)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" className="btn primary" disabled={loading || !query.trim()}>
            {loading ? 'Đang tìm…' : 'Tìm kiếm'}
          </button>
        </div>
      </form>

      {error && <p className="error-box" role="alert">{error}</p>}

      {searched && (
        <div className="search-results" aria-live="polite">
          <p className="search-count">
            {hits.length > 0 ? `Tìm thấy ${hits.length} kết quả` : 'Không tìm thấy kết quả phù hợp'}
          </p>
          {hits.length > 0 && (
            <ul className="search-hit-list" aria-label="Danh sách kết quả tìm kiếm">
              {hits.map((hit, index) => (
                <li key={index} className="search-hit-card">
                  <div className="search-hit-body">
                    <p className="search-snippet">{hit.snippet || hit.quote}</p>
                    <div className="search-hit-citations">
                      <CitationBadge
                        source={hit}
                        documentName={hit.doc_name}
                        jobId={jobId}
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

export default WorkspaceSearch;
