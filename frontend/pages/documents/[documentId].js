import Head from 'next/head';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { getSession } from '../../lib/session';

export default function Reader({ documentId, initialPage, rawPageParam, returnJobId }) {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(initialPage);
  const [error, setError] = useState('');
  const [errorStatus, setErrorStatus] = useState(null);
  const [needsPreparation, setNeedsPreparation] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

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
      const payload = await response.json();
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
      setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setPage(initialPage);
    load(controller.signal);
    return () => controller.abort();
  }, [documentId]);

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
        throw new Error(payload.detail?.message || payload.detail || 'Không thể chuẩn bị bản đọc.');
      }
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function changePage(next) {
    if (data?.page_count && (next < 1 || next > data.page_count)) return;
    setPage(next);
    const nextQuery = { ...router.query, documentId, page: next };
    if (returnJobId) nextQuery.job = returnJobId;
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

  return (
    <>
      <Head>
        <title>DocuMind · Đọc tài liệu</title>
      </Head>
      <main className="workspace reader-page">
        <header>
          <a href="/workspace" className="brand">DocuMind.</a>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {returnJobId && (
              <a href={`/results/${returnJobId}`} className="btn return-job-link">
                Quay lại tác vụ #{returnJobId}
              </a>
            )}
            <a href="/workspace" className="btn">Về thư viện</a>
          </div>
        </header>

        <h1>Đọc tài liệu</h1>

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
        {error && errorStatus !== 404 && errorStatus !== 403 && (
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
                <p className="text-layer-snippet">{currentPage.text}</p>
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
  const page = /^\d+$/.test(query.page || '') ? Number(query.page) : 1;
  const returnJobId = /^\d+$/.test(query.job || '') ? query.job : null;
  return {
    props: {
      documentId: params.documentId,
      initialPage: Number.isSafeInteger(page) && page > 0 ? page : 1,
      rawPageParam,
      returnJobId,
    },
  };
}
