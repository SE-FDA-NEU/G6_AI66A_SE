import { useI18n } from '../../lib/i18n';
import { readLocale } from '../../lib/i18n';
import Head from 'next/head';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { getSession } from '../../lib/session';
import DocumentMetadata from '../../components/DocumentMetadata';
import DocumentLabelEditor from '../../components/DocumentLabelEditor';
import DocumentExpiry from '../../components/DocumentExpiry';
import usePageRefresh from '../../lib/use-page-refresh';
import SavedDocumentSummary from '../../components/SavedDocumentSummary';

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
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(end) ||
    start < 0 ||
    end <= start ||
    end > Array.from(pageData.text).length
  ) {
    return {
      requested: true,
      status: 'fallback',
      reason: 'unresolved_span',
      message: 'Exact highlight not available for this passage.',
    };
  }

  const quote = Array.from(pageData.text).slice(start, end).join('');
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
  const { t, locale, errorText } = useI18n();
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
        setError(t("Bạn không có quyền truy cập tài liệu này (Access denied)."));
        return;
      }
      if (response.status === 404) {
        setErrorStatus(404);
        setError(t("Không tìm thấy tài liệu."));
        return;
      }
      if (response.status === 410) {
        setErrorStatus(410);
        setError(t("Nguồn đã hết hạn và không còn khả dụng. Nội dung cũ không thể mở hoặc khôi phục từ liên kết này."));
        return;
      }
      const payload = await response.json();
      if (signal?.aborted) return;
      if (!response.ok) {
        setNeedsPreparation(response.status === 409);
        setErrorStatus(response.status);
        throw new Error(payload.detail?.message || payload.detail || t("Không thể mở tài liệu này."));
      }
      setData(payload);
      setNeedsPreparation(false);
      setError('');
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || t("Lỗi khi tải tài liệu."));
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
        throw new Error(payload.detail?.message || payload.detail || t("Không thể chuẩn bị bản đọc."));
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
      const points = Array.from(text);
      const offsets = [];
      const lowerText = points.map((char, index) => { const folded = char.toLowerCase(); offsets.push(...Array(folded.length).fill(index)); return folded; }).join('');
      let idx = 0;
      while (idx < lowerText.length) {
        const matchPos = lowerText.indexOf(lowerQ, idx);
        if (matchPos === -1) break;
        found.push({
          matchIndex: found.length,
          page: p.page,
          start: offsets[matchPos],
          end: offsets[matchPos + lowerQ.length - 1] + 1,
          quote: points.slice(offsets[matchPos], offsets[matchPos + lowerQ.length - 1] + 1).join(''),
        });
        idx = matchPos + Math.max(1, lowerQ.length);
      }
    });

    setSearchMatches(found);
    setSearchPerformed(true);

    if (found.length > 0) {
      setActiveMatchIndex(0);
      const firstMatch = found[0];
      changePage(firstMatch.page, q);
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
    const nextQuery = { ...router.query };
    delete nextQuery.search;
    router.replace({ pathname: '/documents/[documentId]', query: nextQuery }, undefined, { shallow: true, scroll: false });
  }

  // Auto-trigger search when data arrives or URL search query changes
  useEffect(() => {
    if (data?.pages) {
      const q = String(router.isReady ? router.query.search || '' : initialSearch).trim();
      if (q && (!searchPerformed || q !== searchQuery)) {
        setSearchInput(q);
        executeSearch(q);
      }
    }
  }, [data?.pages, router.query.search, initialSearch]);


  const currentReturnJobId = (router.isReady && router.query.job !== undefined ? router.query.job : returnJobId) || null;

  function changePage(next, activeSearchOverride) {
    if (data?.page_count && (next < 1 || next > data.page_count)) return;
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

  const pageName = data?.page_kind === 'slide' ? t('Slide') : t("Trang");
  const isInvalidPage = Boolean(
    (rawPageParam != null && (!/^\d+$/.test(rawPageParam) || Number(rawPageParam) < 1)) ||
    (data && (page < 1 || page > data.page_count))
  );

  const currentPage = data?.pages?.find(item => item.page === page);


  // Resolve citation evidence highlight for the current page
  const evidenceId = router.query.evidence || initialEvidenceId || null;
  const rawStart = router.query.start !== undefined ? router.query.start : initialStart;
  const rawEnd = router.query.end !== undefined ? router.query.end : initialEnd;
  const highlightInfo = !evidenceId && page !== initialPage ? { requested: false } : resolveCitationHighlight(evidenceId, rawStart, rawEnd, currentPage);

  // Active search match and matches on current page
  const activeSearchMatch = activeMatchIndex >= 0 && activeMatchIndex < searchMatches.length
    ? searchMatches[activeMatchIndex]
    : null;
  const pdfParams = new URLSearchParams();
  const visibleMatch = activeSearchMatch?.page === page ? activeSearchMatch : null;
  if (searchPerformed && searchQuery && searchMatches.some(match => match.page === page)) {
    pdfParams.set('highlight_page', String(page)); pdfParams.set('q', searchQuery);
  }
  const span = visibleMatch || (highlightInfo.status === 'precise' ? highlightInfo : null);
  if (span) {
    pdfParams.set('highlight_page', String(page));
    pdfParams.set('start', String(span.start)); pdfParams.set('end', String(span.end));
  }
  const hasHighlightGeometry = (currentPage?.positions || []).some(position => Array.isArray(position.bbox) && position.bbox.length === 4
    && (!span || (position.start < span.end && position.end > span.start)));
  const pdfUrl = data ? `/api${data.reader_url}${pdfParams.size ? `&${pdfParams}` : ''}#page=${page}` : '';

  return (
    <>
      <Head>
        <title>{t("DocuMind · Đọc tài liệu")}</title>
      </Head>
      <main className="workspace reader-page">
        <header>
          <a href="/workspace" className="brand">{t("DocuMind.")}</a>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {currentReturnJobId && (
              <a
                href={`/results/${currentReturnJobId}`}
                className="btn return-job-link"
                aria-label={t("Back to Results · Quay lại tác vụ #{0}", currentReturnJobId)}
              >{t("Back to Results")}</a>
            )}
            <a
              href="/workspace"
              className="btn return-workspace-link"
              aria-label={t("Back to Workspace · Về thư viện")}
            >{t("Back to Workspace")}</a>
          </div>
        </header>

        <h1>{t("Đọc tài liệu")}</h1>
        {data?.reader_layout === 'text' && (
          <p role="note">
            {data.file_format === 'DOCX'
              ? t("Đây là bản đọc văn bản. Số trang theo bản đọc này có thể khác tệp Word gốc.")
              : t("Đây là bản đọc văn bản, mỗi slide tương ứng một trang. Hình ảnh và bố cục có thể khác tệp gốc.")}
          </p>
        )}

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
            onUnavailable={() => { setData(null); setNeedsPreparation(false); setErrorStatus(410); setError(t("Nguồn đã hết hạn và không còn khả dụng.")); }}
            onSaved={saved => setData(current => ({
            ...current, user_label: saved.user_label, review_state: saved.review_state,
            last_accessed_at: saved.last_accessed_at, expires_at: saved.expires_at,
          }))} />
          </>
        )}

        {/* Loading state */}
        {loading && !error && !busy && (
          <p role="status" className="reader-loading">{t("Đang mở tài liệu…")}</p>
        )}

        {/* Missing state (404) */}
        {errorStatus === 404 && (
          <div className="reader-error error-box" role="alert">
            <p>{t("Không tìm thấy tài liệu.")}</p>
            <a href="/workspace" className="btn">{t("Về thư viện")}</a>
          </div>
        )}

        {/* Access denied state (403) */}
        {errorStatus === 403 && (
          <div className="reader-error error-box" role="alert">
            <p>{t("Bạn không có quyền truy cập tài liệu này (Access denied).")}</p>
            <a href="/workspace" className="btn">{t("Về thư viện")}</a>
          </div>
        )}

        {/* Generic or conversion errors */}
        {errorStatus === 410 && <div className="reader-error error-box" role="alert">
          <p>{t("Nguồn đã hết hạn và không còn khả dụng. Nội dung cũ không thể mở hoặc khôi phục từ liên kết này.")}</p>
          <a className="btn" href="/workspace">{t("Về thư viện")}</a>
        </div>}
        {error && errorStatus !== 404 && errorStatus !== 403 && errorStatus !== 410 && (
          <p role="alert" className="error-box">{errorText(error)}</p>
        )}

        {needsPreparation && (
          <button className="btn" disabled={busy} onClick={prepare}>
            {busy ? t("Đang chuyển đổi…") : t("Chuẩn bị bản đọc")}
          </button>
        )}

        {/* Invalid page state */}
        {!error && data && isInvalidPage && (
          <div className="reader-invalid-page error-box" role="alert">
            <p>{t("Trang nguồn không tồn tại trong bản đọc này (Tài liệu có") + " "}{data.page_count} {pageName.toLowerCase()}).</p>
            <button className="btn" onClick={() => changePage(1)}>{t("Về trang 1")}</button>
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
              >{t("Trước")}</button>
              <label>
                {pageName}
                <select
                  aria-label={t("Chọn trang nguồn")}
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
              >{t("Sau")}</button>
              <a href={pdfUrl} target="_blank" rel="noreferrer" className="btn">{t("Mở bản PDF")}</a>
            </div>

            {/* In-Document Search Bar (US04) */}
            <div className="reader-search-bar" role="search" aria-label={t("Tìm kiếm trong tài liệu")}>
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
                    placeholder={t("Tìm kiếm trong tài liệu (ví dụ: inflation causes)...")}
                    value={searchInput}
                    onChange={(e) => {
                      setSearchInput(e.target.value);
                      if (!e.target.value.trim()) {
                        clearSearch();
                      }
                    }}
                    aria-label={t("Tìm kiếm trong văn bản tài liệu")}
                  />
                  <button
                    type="submit"
                    className="btn btn-search"
                    data-testid="reader-search-button"
                    aria-label={t("Tìm")}
                  >{t("Tìm")}</button>
                  {searchInput && (
                    <button
                      type="button"
                      className="btn btn-clear-search"
                      data-testid="reader-search-clear"
                      onClick={clearSearch}
                      aria-label={t("Xóa tìm kiếm")}
                    >{t("Xóa")}</button>
                  )}
                </div>
              </form>

              {/* Match Counter & Navigation */}
              {searchPerformed && searchMatches.length > 0 && (
                <div className="reader-search-nav" aria-label={t("Điều hướng kết quả tìm kiếm")}>
                  <span className="search-match-count" data-testid="search-match-count">
                    {activeMatchIndex + 1}/{searchMatches.length}{" " + t("kết quả")}</span>
                  <div className="search-nav-buttons">
                    <button
                      type="button"
                      className="btn btn-nav-match prev-match-btn"
                      data-testid="prev-match-btn"
                      onClick={goToPrevMatch}
                      aria-label={t("Kết quả trước")}
                      title={t("Kết quả trước")}
                    >{t("Trước")}</button>
                    <button
                      type="button"
                      className="btn btn-nav-match next-match-btn"
                      data-testid="next-match-btn"
                      onClick={goToNextMatch}
                      aria-label={t("Kết quả tiếp theo")}
                      title={t("Kết quả tiếp theo")}
                    >{t("Sau")}</button>
                  </div>
                </div>
              )}

              {/* No results state */}
              {searchPerformed && searchMatches.length === 0 && (
                <p className="search-no-results" role="status" data-testid="search-no-results">{t("Không tìm thấy kết quả phù hợp cho \"")}{searchQuery}".
                </p>
              )}
            </div>

            {/* Fallback notice for scanned pages or unresolved evidence spans */}
            {highlightInfo.requested && highlightInfo.status === 'fallback' && (
              <div className="highlight-fallback-notice" role="status">
                <p className="fallback-message">{t("Exact highlight not available for this passage.")}</p>
              </div>
            )}

            {(span || pdfParams.size > 0) && hasHighlightGeometry && <p className="reader-highlight-note" role="status">{t("Kết quả được tô sáng trực tiếp trên tài liệu; vị trí đang chọn có màu cam.")}</p>}

            {(span || pdfParams.size > 0) && !hasHighlightGeometry && <p role="status" className="highlight-fallback-notice">{t("Trang này chưa có đủ tọa độ chữ để tô sáng trực tiếp. Bạn vẫn có thể xem tài liệu và bản tóm tắt bên dưới.")}</p>}

            <iframe
              className="reader-pdf"
              src={pdfUrl}
              title={t("Bản đọc PDF — {0} {1}", pageName, page)}
            />

            <SavedDocumentSummary key={documentId} documentId={documentId} jobId={currentReturnJobId} readerVersion={data.reader_version}/>

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
      initialLocale: readLocale(req.headers.cookie),
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

