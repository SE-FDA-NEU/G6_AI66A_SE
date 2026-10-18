import Head from 'next/head';
import { useState } from 'react';
import { getSession } from '../lib/session';
import WorkspaceSearch from '../components/WorkspaceSearch';
import WorkspaceDocumentList from '../components/WorkspaceDocumentList';
import WorkspaceNavigation from '../components/WorkspaceNavigation';
import WorkspaceFolders from '../components/WorkspaceFolders';
import useFolders from '../lib/use-folders';
import WorkspaceLabelFilter from '../components/WorkspaceLabelFilter';

export default function Workspace({ user }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const folderState = useFolders();
  const [selectedFolder, setSelectedFolder] = useState('');
  const [aiLabel, setAiLabel] = useState('');
  const [revision, setRevision] = useState(0);
  const [moveMessage, setMoveMessage] = useState('');

  function documentMoved(document) {
    const folder = folderState.folders.find(item => item.id === document.folder_id);
    setMoveMessage(`Đã chuyển “${document.original_filename}” ${document.folder_id == null ? 'về Chưa phân thư mục' : `tới “${folder?.name || 'thư mục đã chọn'}”`}.`);
    setRevision(value => value + 1);
  }

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

          <WorkspaceFolders {...folderState} selected={selectedFolder} onSelect={setSelectedFolder} />
          {moveMessage && <p role="status">{moveMessage}</p>}
          <WorkspaceSearch folders={folderState.folders} foldersUnavailable={folderState.loading || Boolean(folderState.error)} refreshKey={revision} />

          <WorkspaceLabelFilter label={aiLabel} folderName={folderState.folders.find(folder => String(folder.id) === selectedFolder)?.name}
            hasFolder={Boolean(selectedFolder)} onApply={setAiLabel} onClear={() => setAiLabel('')}
            onClearAll={() => { setAiLabel(''); setSelectedFolder(''); }} />
          <WorkspaceDocumentList key={JSON.stringify([selectedFolder, aiLabel])} folderId={selectedFolder} aiLabel={aiLabel} folders={folderState.folders}
            foldersUnavailable={folderState.loading || Boolean(folderState.error)} refreshKey={revision} onMoved={documentMoved} />
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

