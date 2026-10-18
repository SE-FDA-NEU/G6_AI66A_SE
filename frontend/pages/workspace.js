import Head from 'next/head';
import { useState } from 'react';
import { getSession } from '../lib/session';
import WorkspaceSearch from '../components/WorkspaceSearch';
import WorkspaceDocumentList from '../components/WorkspaceDocumentList';
import WorkspaceNavigation from '../components/WorkspaceNavigation';

export default function Workspace({ user }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

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
          <WorkspaceNavigation><button className="btn" onClick={logout} disabled={busy}>
            Đăng xuất
          </button></WorkspaceNavigation>
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

          <WorkspaceDocumentList />
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

