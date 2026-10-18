import Head from 'next/head';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { getSession } from '../../lib/session';
import DocumentMetadata from '../../components/DocumentMetadata';
import DocumentLabelEditor from '../../components/DocumentLabelEditor';
import DocumentExpiry from '../../components/DocumentExpiry';
import usePageRefresh from '../../lib/use-page-refresh';

export function resolveCitationHighlight(evidenceId, rawStart, rawEnd, pageData) {
  if (!evidenceId && rawStart == null && rawEnd == null) {
    return { requested: false };
  }

  let start = rawStart != null ? Number(rawStart) : null;
  let end = rawEnd != null ? Number(rawEnd) : null;
  let evidencePage = null;

  // Try parsing offsets from evidenceId (format: docId-page-start-end) if start/end are missing
  if (evidenceId) {
    const parts = String(evidenceId).split('-');
    if (parts.length >= 4) {
      const p = Number(parts[parts.length - 3]);
      const s = Number(parts[parts.length - 2]);
      const e = Number(parts[parts.length - 1]);
      if (Number.isSafeInteger(p) && p > 0) {
        evidencePage = p;
      }
      if ((start == null || end == null || isNaN(start) || isNaN(end)) &&
          Number.isSafeInteger(s) && Number.isSafeInteger(e)) {
        start = s;
        end = e;
      }
    }
  }

  // If evidence is explicitly for another page, don't attempt highlight on current page
  if (evidencePage != null && pageData?.page && evidencePage !== pageData.page) {
    return { requested: false };
  }

  // Fallback 1: Scanned page without text layer
  if (!pageData || !pageData.text || !pageData.text.trim()) {
    return {
      requested: true,
      status: 'fallback',
      reason: 'scanned_page',
      message: 'Exact highlight not available for this passage.',
    };
  }

  // Fallback 2: Unresolved or out-of-bounds span
  if (
    start == null ||
    end == null ||
    isNaN(start) ||
    isNaN(end) ||
    start < 0 ||
    end <= start ||
    end > pageData.text.length
  ) {
    return {
      requested: true,
      status: 'fallback',
      reason: 'unresolved_span',
      message: 'Exact highlight not available for this passage.',
    };
  }

  const quote = pageData.text.slice(start, end);
  const matchingPositions = Array.isArray(pageData.positions)
    ? pageData.positions.filter(pos => pos.start >= start && pos.end <= end)
    : [];

  return {
    requested: true,
    status: 'precise',
    start,
    end,
    quote,
    matchingPositions,
    evidenceId: evidenceId || `${pageData.page}-${start}-${end}`,
  };
}

export function renderTextWithSearchHighlights(text, pageMatches, activeMatch) {
  if (!pageMatches || pageMatches.length === 0) return text;
  const sorted = [...pageMatches].sort((a, b) => a.start - b.start);
  const result = [];
  let currentIdx = 0;

  sorted.forEach((m, idx) => {
    if (m.start < currentIdx) return;
    if (m.start > currentIdx) {
      result.push(<span key={`text-${currentIdx}`}>{text.slice(currentIdx, m.start)}</span>);
    }
    const isActive = Boolean(
      activeMatch &&
      activeMatch.page === m.page &&
      activeMatch.start === m.start &&
      activeMatch.end === m.end
    );
    result.push(
      <mark
        key={`match-${m.page}-${m.start}-${idx}`}
        className={`search-highlight ${isActive ? 'active-match' : 'other-match'}`}
        data-testid="search-highlight"
        data-is-active={isActive ? 'true' : 'false'}
        data-start={m.start}
        data-end={m.end}
      >
        {text.slice(m.start, m.end)}
      </mark>
    );
    currentIdx = m.end;
  });

  if (currentIdx < text.length) {
    result.push(<span key="text-tail">{text.slice(currentIdx)}</span>);
  }
  return result;
}

export default function Reader({
  documentId,
  initialPage,
  rawPageParam,
  returnJobId,
  initialEvidenceId,
  initialStart,
  initialEnd,
  initialSearch = '',
}) {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(initialPage);
  const [error, setError] = useState('');
  const [errorStatus, setErrorStatus] = useState(null);
  const [needsPreparation, setNeedsPreparation] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  usePageRefresh(() => setRevision(value => value + 1));

  // In-document text search states (US04)
  const [searchInput, setSearchInput] = useState(initialSearch);
  const [searchQuery, setSearchQuery] = useState(initialSearch);
  const [searchMatches, setSearchMatches] = useState([]);
  const [activeMatchIndex, setActiveMatchIndex] = useState(-1);
  const [searchPerformed, setSearchPerformed] = useState(false);

  // Sync with router.query.page on client-side navigation (e.g. browser back/forward)
  useEffect(() => {
    if (!router.isReady) return;
    const qPageStr = router.query.page;
    if (qPageStr !== undefined) {
      const qPage = Number(qPageStr);
      if (Number.isSafeInteger(qPage) && qPage > 0) {
        setPage(qPage);
      }
    }
  }, [router.query.page, router.isReady]);

  async function load(signal) {
    setLoading(true);
    setData(null);
    setNeedsPreparation(false);
    setError('');
    setErrorStatus(null);
    try {
      const response = await fetch(`/api/documents/${documentId}/pages`, { signal, cache: 'no-store' });
      if (response.status === 401) {
        window.location.assign('/');
        return;
      }
      if (response.status === 403) {
        setErrorStatus(403);
        setError('Bạn không có quyền truy cập tài liệu này (Access denied).');
        return;
      }
      if (response.status === 404) {
        setErrorStatus(404);
        setError('Không tìm thấy tài liệu.');
        return;
      }
      if (response.status === 410) {
        setErrorStatus(410);
        setError('Nguồn đã hết hạn và không còn khả dụng. Nội dung cũ không thể mở hoặc khôi phục từ liên kết này.');
        return;
      }
      const payload = await response.json();
      if (signal?.aborted) return;
      if (!response.ok) {
        setNeedsPreparation(response.status === 409);
        setErrorStatus(response.status);
        throw new Error(payload.detail?.message || payload.detail || 'Không thể mở tài liệu này.');
      }
      setData(payload);
      setNeedsPreparation(false);
      setError('');
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Lỗi khi tải tài liệu.');
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    load(controller.signal);
    return () => controller.abort();
  }, [documentId, revision]);
  useEffect(() => { setPage(initialPage); }, [documentId]);

  async function prepare() {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/api/documents/${documentId}/reader`, { method: 'POST' });
      if (response.status === 401) {
        window.location.assign('/');
        return;
      }
      const payload = await response.json();
      if (!response.ok) {
        if (response.status === 410) {
          setData(null); setNeedsPreparation(false); setErrorStatus(410);
        }
        throw new Error(payload.detail?.message || payload.detail || 'Không thể chuẩn bị bản đọc.');
      }
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Search logic across extracted pages (US04)
  function executeSearch(queryOverride) {
    const q = (queryOverride !== undefined ? queryOverride : searchInput).trim();
    setSearchQuery(q);
    if (!q) {
      setSearchMatches([]);
      setActiveMatchIndex(-1);
      setSearchPerformed(false);
      return;
    }

    if (!data?.pages || !Array.isArray(data.pages)) {
      setSearchMatches([]);
      setActiveMatchIndex(-1);
      setSearchPerformed(true);
      return;
    }

    const lowerQ = q.toLowerCase();
    const found = [];

    data.pages.forEach((p) => {
      const text = p.text || '';
      const lowerText = text.toLowerCase();
      let idx = 0;
      while (idx < lowerText.length) {
        const matchPos = lowerText.indexOf(lowerQ, idx);
        if (matchPos === -1) break;
        found.push({
          matchIndex: found.length,
          page: p.page,
          start: matchPos,
          end: matchPos + lowerQ.length,
          quote: text.slice(matchPos, matchPos + lowerQ.length),
        });
        idx = matchPos + Math.max(1, lowerQ.length);
      }
    });

    setSearchMatches(found);
    setSearchPerformed(true);

    if (found.length > 0) {
      setActiveMatchIndex(0);
      const firstMatch = found[0];
      if (firstMatch.page !== page) {
        changePage(firstMatch.page, q);
      }
    } else {
      setActiveMatchIndex(-1);
    }
  }

  function goToNextMatch() {
    if (searchMatches.length === 0) return;
    const nextIdx = (activeMatchIndex + 1) % searchMatches.length;
    setActiveMatchIndex(nextIdx);
    const target = searchMatches[nextIdx];
    if (target.page !== page) {
      changePage(target.page);
    }
  }

  function goToPrevMatch() {
    if (searchMatches.length === 0) return;
    const prevIdx = (activeMatchIndex - 1 + searchMatches.length) % searchMatches.length;
    setActiveMatchIndex(prevIdx);
    const target = searchMatches[prevIdx];
    if (target.page !== page) {
      changePage(target.page);
    }
  }

  function clearSearch() {
    setSearchInput('');
    setSearchQuery('');
    setSearchMatches([]);
    setActiveMatchIndex(-1);
    setSearchPerformed(false);
  }

  // Auto-trigger search when data arrives or URL search query changes
  useEffect(() => {
    if (data?.pages) {
      const q = String(router.query.search || initialSearch || '').trim();
      if (q && (!searchPerformed || q !== searchQuery)) {
        setSearchInput(q);
        executeSearch(q);
      }
    }
  }, [data?.pages, router.query.search, initialSearch]);


  const currentReturnJobId = (router.isReady && router.query.job !== undefined ? router.query.job : returnJobId) || null;

  function changePage(next, activeSearchOverride) {
    if (data?.page_count && (next < 1 || next > data.page_count)) return;
    setPage(next);
    const nextQuery = { ...router.query, documentId, page: next };
    if (currentReturnJobId) nextQuery.job = currentReturnJobId;
    const qToKeep = activeSearchOverride !== undefined ? activeSearchOverride : searchQuery;
    if (qToKeep) nextQuery.search = qToKeep;
    router.push(
      { pathname: '/documents/[documentId]', query: nextQuery },
      undefined,
      { shallow: true, scroll: false }
    );
  }

  const pageName = data?.page_kind === 'slide' ? 'Slide' : 'Trang';
  const isInvalidPage = Boolean(
    (rawPageParam != null && (!/^\d+$/.test(rawPageParam) || Number(rawPageParam) < 1)) ||
    (data && (page < 1 || page > data.page_count))
  );

  const currentPage = data?.pages?.find(item => item.page === page);
  const pdfUrl = data ? `/api${data.reader_url}#page=${page}` : '';

  // Resolve citation evidence highlight for the current page
  const evidenceId = router.query.evidence || initialEvidenceId || null;
  const rawStart = router.query.start !== undefined ? router.query.start : initialStart;
  const rawEnd = router.query.end !== undefined ? router.query.end : initialEnd;
  const highlightInfo = resolveCitationHighlight(evidenceId, rawStart, rawEnd, currentPage);

  // Active search match and matches on current page
  const activeSearchMatch = activeMatchIndex >= 0 && activeMatchIndex < searchMatches.length
    ? searchMatches[activeMatchIndex]
    : null;
  const currentPageMatches = searchMatches.filter(m => m.page === page);

  return (
    <>
      <Head>
        <title>DocuMind · Đọc tài liệu</title>
      </Head>
      <main className="workspace reader-page">
        <header>
          <a href="/workspace" className="brand">DocuMind.</a>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {currentReturnJobId && (
              <a
                href={`/results/${currentReturnJobId}`}
                className="btn return-job-link"
                aria-label={`Back to Results · Quay lại tác vụ #${currentReturnJobId}`}
              >
                Back to Results
              </a>
            )}
            <a
              href="/workspace"
              className="btn return-workspace-link"
              aria-label="Back to Workspace · Về thư viện"
            >
              Back to Workspace
            </a>
          </div>
        </header>

        <h1>Đọc tài liệu</h1>

        {/* Document Metadata (US10) */}
        {!error && data && (
          <>
          <DocumentMetadata
            aiLabel={data.ai_label}
            aiConfidence={data.ai_confidence}
            reviewState={data.review_state}
            userLabel={data.user_label}
            folderId={data.folder_id}
            className="reader-document-metadata"
          />
          <DocumentExpiry expiresAt={data.expires_at} />
          <DocumentLabelEditor key={documentId} documentId={documentId} document={data}
            onUnavailable={() => { setData(null); setNeedsPreparation(false); setErrorStatus(410); setError('Nguồn đã hết hạn và không còn khả dụng.'); }}
            onSaved={saved => setData(current => ({
            ...current, user_label: saved.user_label, review_state: saved.review_state,
            last_accessed_at: saved.last_accessed_at, expires_at: saved.expires_at,
          }))} />
          </>
        )}

        {/* Loading state */}
        {loading && !error && !busy && (
          <p role="status" className="reader-loading">Đang mở tài liệu…</p>
        )}

        {/* Missing state (404) */}
        {errorStatus === 404 && (
          <div className="reader-error error-box" role="alert">
            <p>Không tìm thấy tài liệu.</p>
            <a href="/workspace" className="btn">Về thư viện</a>
          </div>
        )}

        {/* Access denied state (403) */}
        {errorStatus === 403 && (
          <div className="reader-error error-box" role="alert">
            <p>Bạn không có quyền truy cập tài liệu này (Access denied).</p>
            <a href="/workspace" className="btn">Về thư viện</a>
          </div>
        )}

        {/* Generic or conversion errors */}
        {errorStatus === 410 && <div className="reader-error error-box" role="alert">
          <p>Nguồn đã hết hạn và không còn khả dụng. Nội dung cũ không thể mở hoặc khôi phục từ liên kết này.</p>
          <a className="btn" href="/workspace">Về thư viện</a>
        </div>}
        {error && errorStatus !== 404 && errorStatus !== 403 && errorStatus !== 410 && (
          <p role="alert" className="error-box">{error}</p>
        )}

        {needsPreparation && (
          <button className="btn" disabled={busy} onClick={prepare}>
            {busy ? 'Đang chuyển đổi…' : 'Chuẩn bị bản đọc'}
          </button>
        )}

        {/* Invalid page state */}
        {!error && data && isInvalidPage && (
          <div className="reader-invalid-page error-box" role="alert">
            <p>Trang nguồn không tồn tại trong bản đọc này (Tài liệu có {data.page_count} {pageName.toLowerCase()}).</p>
            <button className="btn" onClick={() => changePage(1)}>Về trang 1</button>
          </div>
        )}

        {/* Valid reader content */}
        {!error && data && !isInvalidPage && (
          <>
            <div className="reader-controls">
              <button
                className="btn"
                disabled={page <= 1}
                onClick={() => changePage(page - 1)}
              >
                Trước
              </button>
              <label>
                {pageName}
                <select
                  aria-label="Chọn trang nguồn"
                  value={page}
                  onChange={event => changePage(Number(event.target.value))}
                >
                  {data.pages.map(item => (
                    <option key={item.page} value={item.page}>
                      {pageName} {item.page}
                    </option>
                  ))}
                </select>
              </label>
              <span className="reader-page-indicator">
                {pageName} {page}/{data.page_count}
              </span>
              <button
                className="btn"
                disabled={page >= data.page_count}
                onClick={() => changePage(page + 1)}
              >
                Sau
              </button>
              <a href={pdfUrl} target="_blank" rel="noreferrer" className="btn">
                Mở bản PDF
              </a>
            </div>

            {/* In-Document Search Bar (US04) */}
            <div className="reader-search-bar" role="search" aria-label="Tìm kiếm trong tài liệu">
              <form
                className="reader-search-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  executeSearch();
                }}
              >
                <div className="search-input-group">
                  <input
                    id="reader-search-input"
                    data-testid="reader-search-input"
                    type="search"
                    placeholder="Tìm kiếm trong tài liệu (ví dụ: inflation causes)..."
                    value={searchInput}
                    onChange={(e) => {
                      setSearchInput(e.target.value);
                      if (!e.target.value.trim()) {
                        clearSearch();
                      }
                    }}
                    aria-label="Tìm kiếm trong văn bản tài liệu"
                  />
                  <button
                    type="submit"
                    className="btn btn-search"
                    data-testid="reader-search-button"
                    aria-label="Tìm"
                  >
                    Tìm
                  </button>
                  {searchInput && (
                    <button
                      type="button"
                      className="btn btn-clear-search"
                      data-testid="reader-search-clear"
                      onClick={clearSearch}
                      aria-label="Xóa tìm kiếm"
                    >
                      Xóa
                    </button>
                  )}
                </div>
              </form>

              {/* Match Counter & Navigation */}
              {searchPerformed && searchMatches.length > 0 && (
                <div className="reader-search-nav" aria-label="Điều hướng kết quả tìm kiếm">
                  <span className="search-match-count" data-testid="search-match-count">
                    {activeMatchIndex + 1}/{searchMatches.length} kết quả
                  </span>
                  <div className="search-nav-buttons">
                    <button
                      type="button"
                      className="btn btn-nav-match prev-match-btn"
                      data-testid="prev-match-btn"
                      onClick={goToPrevMatch}
                      aria-label="Kết quả trước"
                      title="Kết quả trước"
                    >
                      Trước
                    </button>
                    <button
                      type="button"
                      className="btn btn-nav-match next-match-btn"
                      data-testid="next-match-btn"
                      onClick={goToNextMatch}
                      aria-label="Kết quả tiếp theo"
                      title="Kết quả tiếp theo"
                    >
                      Sau
                    </button>
                  </div>
                </div>
              )}

              {/* No results state */}
              {searchPerformed && searchMatches.length === 0 && (
                <p className="search-no-results" role="status" data-testid="search-no-results">
                  Không tìm thấy kết quả phù hợp cho "{searchQuery}".
                </p>
              )}
            </div>

            {/* Fallback notice for scanned pages or unresolved evidence spans */}
            {highlightInfo.requested && highlightInfo.status === 'fallback' && (
              <div className="highlight-fallback-notice" role="status">
                <p className="fallback-message">Exact highlight not available for this passage.</p>
              </div>
            )}

            {/* Highlighted passage card for active search result */}
            {activeSearchMatch && activeSearchMatch.page === page && (
              <div className="search-match-card highlighted-passage-card" role="region" aria-label="Đoạn văn bản tìm kiếm được chọn">
                <div className="highlighted-passage-header">
                  <strong>Kết quả tìm kiếm ({activeMatchIndex + 1}/{searchMatches.length}) — {pageName} {page}:</strong>
                  <span className="search-match-badge" data-testid="search-match-badge">
                    Vị trí: {activeSearchMatch.start} - {activeSearchMatch.end}
                  </span>
                </div>
                <p className="highlighted-passage-quote">"{activeSearchMatch.quote}"</p>
              </div>
            )}

            {/* Highlighted passage card when citation resolved and no active search on current page */}
            {(!activeSearchMatch || activeSearchMatch.page !== page) && highlightInfo.status === 'precise' && (
              <div className="highlighted-passage-card" role="region" aria-label="Đoạn trích dẫn được tô sáng">
                <div className="highlighted-passage-header">
                  <strong>Đoạn trích dẫn bằng chứng (#{highlightInfo.evidenceId}):</strong>
                  {highlightInfo.matchingPositions?.length > 0 && (
                    <span className="stored-positions-tag" data-positions-count={highlightInfo.matchingPositions.length}>
                      {highlightInfo.matchingPositions.length} vị trí tọa độ
                    </span>
                  )}
                </div>
                <p className="highlighted-passage-quote">"{highlightInfo.quote}"</p>
              </div>
            )}

            <iframe
              className="reader-pdf"
              src={pdfUrl}
              title={`Bản đọc PDF — ${pageName} ${page}`}
            />

            {/* Text layer preview where available */}
            {currentPage?.text ? (
              <div className="reader-text-layer" aria-label="Lớp chữ trang nguồn">
                <div className="text-layer-header">
                  <strong>Lớp chữ {pageName.toLowerCase()} {page}:</strong>
                </div>
                {currentPageMatches.length > 0 ? (
                  <p className="text-layer-snippet text-layer-rendered">
                    {renderTextWithSearchHighlights(currentPage.text, currentPageMatches, activeSearchMatch)}
                  </p>
                ) : highlightInfo.status === 'precise' ? (
                  <p className="text-layer-snippet text-layer-rendered">
                    <span className="text-before">{currentPage.text.slice(0, highlightInfo.start)}</span>
                    <mark
                      className="citation-highlight"
                      data-evidence-id={highlightInfo.evidenceId}
                      data-start={highlightInfo.start}
                      data-end={highlightInfo.end}
                      data-positions-count={highlightInfo.matchingPositions?.length || 0}
                    >
                      {highlightInfo.quote}
                    </mark>
                    <span className="text-after">{currentPage.text.slice(highlightInfo.end)}</span>
                  </p>
                ) : (
                  <p className="text-layer-snippet">{currentPage.text}</p>
                )}
              </div>
            ) : (
              <p role="status" className="text-layer-empty">
                Trang này không có lớp chữ để highlight chính xác.
              </p>
            )}
          </>
        )}

      </main>
    </>
  );
}

export async function getServerSideProps({ req, res, params, query }) {
  res.setHeader('Cache-Control', 'no-store');
  if (!await getSession(req)) return { redirect: { destination: '/', permanent: false } };
  if (!/^[1-9]\d*$/.test(params.documentId)) return { notFound: true };
  const rawPageParam = query.page ?? null;
  let page = /^\d+$/.test(query.page || '') ? Number(query.page) : null;
  if (!page && query.evidence) {
    const parts = String(query.evidence).split('-');
    if (parts.length >= 4) {
      const p = Number(parts[parts.length - 3]);
      if (Number.isSafeInteger(p) && p > 0) {
        page = p;
      }
    }
  }
  if (!page) page = 1;
  const returnJobId = query.job && /^[a-zA-Z0-9_-]+$/.test(String(query.job)) ? String(query.job) : null;
  const initialEvidenceId = query.evidence ?? null;
  const initialStart = /^\d+$/.test(query.start || '') ? Number(query.start) : null;
  const initialEnd = /^\d+$/.test(query.end || '') ? Number(query.end) : null;
  const initialSearch = query.search && typeof query.search === 'string' ? String(query.search).trim() : '';
  return {
    props: {
      documentId: params.documentId,
      initialPage: Number.isSafeInteger(page) && page > 0 ? page : 1,
      rawPageParam,
      returnJobId,
      initialEvidenceId,
      initialStart,
      initialEnd,
      initialSearch,
    },
  };
}

