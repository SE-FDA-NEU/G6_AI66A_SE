import Head from 'next/head';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { getSession } from '../../lib/session';

export default function Reader({ documentId, initialPage }) {
  const router = useRouter();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(initialPage);
  const [error, setError] = useState('');
  const [needsPreparation, setNeedsPreparation] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load(signal) {
    const response = await fetch(`/api/documents/${documentId}/pages`, { signal, cache: 'no-store' });
    if (response.status === 401) { window.location.assign('/'); return; }
    const payload = await response.json();
    if (!response.ok) {
      setNeedsPreparation(response.status === 409);
      throw new Error(payload.detail?.message || 'Không thể mở tài liệu này.');
    }
    if (initialPage > payload.page_count) {
      setNeedsPreparation(false);
      throw new Error('Trang nguồn không tồn tại trong bản đọc này.');
    }
    setData(payload);
    setNeedsPreparation(false);
    setError('');
  }

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError('');
    setNeedsPreparation(false);
    setPage(initialPage);
    load(controller.signal).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [documentId, initialPage]);

  async function prepare() {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/api/documents/${documentId}/reader`, { method: 'POST' });
      if (response.status === 401) { window.location.assign('/'); return; }
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail?.message || 'Không thể chuẩn bị bản đọc.');
      await load();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function changePage(next) {
    setPage(next);
    router.replace({ pathname: '/documents/[documentId]', query: { documentId, page: next } },
                   undefined, { shallow: true, scroll: false });
  }

  const pageName = data?.page_kind === 'slide' ? 'Slide' : 'Trang';
  const pdfUrl = data ? `/api${data.reader_url}#page=${page}` : '';
  return <><Head><title>DocuMind · Đọc tài liệu</title></Head>
    <main className="workspace reader-page"><header><a href="/workspace" className="brand">DocuMind.</a>
      <a href="/workspace" className="btn">Về thư viện</a></header>
      <h1>Đọc tài liệu</h1>
      {error && <p role="alert" className="error-box">{error}</p>}
      {needsPreparation && <button className="btn" disabled={busy} onClick={prepare}>{busy ? 'Đang chuyển đổi…' : 'Chuẩn bị bản đọc'}</button>}
      {!data && !error && !busy && <p role="status">Đang mở tài liệu…</p>}
      {data && <>
        <div className="reader-controls"><button className="btn" disabled={page <= 1} onClick={() => changePage(page - 1)}>Trước</button>
          <label>{pageName}<select aria-label="Chọn trang nguồn" value={page} onChange={event => changePage(Number(event.target.value))}>
            {data.pages.map(item => <option key={item.page} value={item.page}>{pageName} {item.page}</option>)}</select></label>
          <span>{pageName} {page}/{data.page_count}</span>
          <button className="btn" disabled={page >= data.page_count} onClick={() => changePage(page + 1)}>Sau</button>
          <a href={pdfUrl} target="_blank" rel="noreferrer" className="btn">Mở bản PDF</a>
        </div>
        <iframe className="reader-pdf" src={pdfUrl} title={`Bản đọc PDF — ${pageName} ${page}`} />
        {!data.pages.find(item => item.page === page)?.text && <p role="status">Trang này không có lớp chữ để highlight chính xác.</p>}
      </>}
    </main></>;
}

export async function getServerSideProps({ req, res, params, query }) {
  res.setHeader('Cache-Control', 'no-store');
  if (!await getSession(req)) return { redirect: { destination: '/', permanent: false } };
  if (!/^[1-9]\d*$/.test(params.documentId)) return { notFound: true };
  const page = /^\d+$/.test(query.page || '') ? Number(query.page) : 1;
  return { props: { documentId: params.documentId, initialPage: Number.isSafeInteger(page) && page > 0 ? page : 1 } };
}
