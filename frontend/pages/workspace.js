import Head from 'next/head';
import { useEffect, useState } from 'react';
import { getSession } from '../lib/session';
import WorkspaceSearch from '../components/WorkspaceSearch';
import DocumentMetadata from '../components/DocumentMetadata';

export default function Workspace({ user }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);

  useEffect(() => {
    async function loadDocuments() {
      try {
        const res = await fetch('/api/documents');
        if (res.ok) {
          const data = await res.json();
          setDocuments(Array.isArray(data) ? data : []);
        }
      } catch {
        // Keep search and upload operational if listing fails
      } finally {
        setLoadingDocs(false);
      }
    }
    loadDocuments();
  }, []);

  async function logout() {
    setBusy(true);
    try {
      const response = await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) throw new Error();
      window.location.assign('/');
    } catch {
      setError('Không thể đăng xuất. Vui lòng thử lại.');
      setBusy(false);
    }
  }

  return (
    <>
      <Head>
        <title>DocuMind · Không gian tài liệu</title>
      </Head>
      <main className="workspace">
        <header>
          <a href="/workspace" className="brand">
            DocuMind<span className="brand-dot">.</span>
          </a>
          <button className="btn" onClick={logout} disabled={busy}>
            Đăng xuất
          </button>
        </header>
        <section className="workspace-content">
          <p className="eyebrow">CHÀO MỪNG, {user.username}</p>
          <h1>Không gian tài liệu</h1>
          <p>Bạn đã đăng nhập với {user.email}.</p>
          <a className="btn upload-link" href="/upload">
            Tải tài liệu
          </a>
          <div role="alert">{error && <p className="error-box">{error}</p>}</div>

          <WorkspaceSearch />

          <section className="workspace-documents" aria-label="Danh sách tài liệu">
            <h2>Tài liệu của bạn</h2>
            {loadingDocs && <p className="muted">Đang tải danh sách tài liệu…</p>}
            {!loadingDocs && documents.length === 0 && (
              <p className="muted">Chưa có tài liệu nào trong không gian làm việc.</p>
            )}
            {!loadingDocs && documents.length > 0 && (
              <ul className="workspace-document-list" aria-label="Danh sách tài liệu workspace">
                {documents.map((doc) => (
                  <li
                    key={doc.id}
                    className="workspace-document-row"
                    data-testid="workspace-document-row"
                    data-document-id={doc.id}
                  >
                    <div className="document-row-main">
                      <a href={`/documents/${doc.id}?page=1`} className="document-row-title">
                        <strong>{doc.original_filename}</strong>
                      </a>
                      <DocumentMetadata
                        aiLabel={doc.ai_label}
                        aiConfidence={doc.ai_confidence}
                        reviewState={doc.review_state}
                        userLabel={doc.user_label}
                        folderId={doc.folder_id}
                        className="workspace-metadata-row"
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </section>
      </main>
    </>
  );
}

export async function getServerSideProps({ req, res }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  return user ? { props: { user } } : { redirect: { destination: '/', permanent: false } };
}

