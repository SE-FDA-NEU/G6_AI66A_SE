import Head from 'next/head';
import { useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { FileText, Plus, PanelLeftClose, PanelLeftOpen, Folder } from 'lucide-react';
import { useI18n } from '../lib/i18n';
import { ui } from '../lib/ui';
import useFolders from '../lib/use-folders';
import usePageRefresh from '../lib/use-page-refresh';
import DocumentHistory from './DocumentHistory';
import DocumentUpload from './DocumentUpload';
import WorkspaceFolders from './WorkspaceFolders';
import WorkspaceNavigation from './WorkspaceNavigation';

export default function WorkspaceHome({ user }) {
  const { t } = useI18n();
  const router = useRouter();
  const folderState = useFolders();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [folderOpen, setFolderOpen] = useState(false);
  const [revision, setRevision] = useState(0);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const foldersPanel = useRef(null);
  const requested = router.query.folder;
  const selectedFolder = typeof requested === 'string' && /^(unassigned|[1-9]\d*)$/.test(requested) ? requested : '';
  usePageRefresh(() => setRevision(value => value + 1));

  function openFolder(id) {
    router.push({ pathname: '/workspace', query: id ? { folder: id } : {} }, undefined, { shallow: true, scroll: false });
  }
  function saved(document) {
    setMessage(t('Đã cập nhật “{0}”.', document.original_filename));
    setRevision(value => value + 1);
  }
  function createFolder() {
    setFolderOpen(true);
    requestAnimationFrame(() => foldersPanel.current?.querySelector('input')?.focus());
  }
  async function logout() {
    setBusy(true);
    try {
      const response = await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) throw new Error();
      window.location.assign('/');
    } catch { setError(t('Không thể đăng xuất. Vui lòng thử lại.')); setBusy(false); }
  }
  const currentFolder = folderState.folders.find(folder => String(folder.id) === selectedFolder);
  const destinationId = selectedFolder && selectedFolder !== 'unassigned' ? Number(selectedFolder) : null;
  const folderReady = destinationId == null || (!folderState.loading && !folderState.error && Boolean(currentFolder));

  return <>
    <Head><title>{t('DocuMind · Không gian tài liệu')}</title></Head>
    <div className="mx-auto grid min-h-screen max-w-7xl border-x border-line md:grid-cols-[280px_minmax(0,1fr)]">
      <aside aria-label={t('Thanh bên thư viện')} className="workspace-sidebar min-w-0 border-b border-line bg-surface md:sticky md:top-0 md:flex md:h-screen md:flex-col md:border-r md:border-b-0">
        <div className="flex min-h-16 items-center justify-between gap-3 px-4">
          <a href="/workspace" className={ui('brand')}><FileText size={20} className="text-orange-400"/>DocuMind<span className="text-orange-400">.</span></a>
          <button type="button" className="grid size-11 place-items-center text-zinc-400 md:hidden" aria-expanded={sidebarOpen} aria-controls="document-history-sidebar" aria-label={t(sidebarOpen ? 'Đóng lịch sử' : 'Mở lịch sử')} onClick={() => setSidebarOpen(value => !value)}>{sidebarOpen ? <PanelLeftClose size={18}/> : <PanelLeftOpen size={18}/>}</button>
        </div>
        <div id="document-history-sidebar" className={`${sidebarOpen ? 'flex' : 'hidden'} min-h-0 flex-col gap-5 px-4 pb-5 md:flex md:flex-1 md:overflow-y-auto`} onKeyDown={event => { if (event.key === 'Escape') { setSidebarOpen(false); document.querySelector('[aria-controls="document-history-sidebar"]')?.focus(); } }}>
          <button type="button" className={ui('btn primary w-full')} aria-expanded={folderOpen} aria-controls="create-folder-panel" onClick={() => folderOpen ? setFolderOpen(false) : createFolder()}><Plus size={16}/>{t('Tạo thư mục')}</button>
          <div ref={foldersPanel} id="create-folder-panel" hidden={!folderOpen}><WorkspaceFolders add={folderState.add}/></div>
          {message && <p role="status" className="text-xs leading-6 text-emerald-400">{message}</p>}
          <DocumentHistory folderId={selectedFolder} folders={folderState.folders} foldersUnavailable={folderState.loading || Boolean(folderState.error)} foldersLoading={folderState.loading} folderError={Boolean(folderState.error)} onRetryFolders={folderState.reload} onSelectFolder={openFolder} refreshKey={revision} onMoved={saved} onLabelSaved={saved} onCreateFolder={createFolder}/>
          <div className="mt-auto flex items-center gap-3 border-t border-line pt-5 text-xs"><span className="grid size-8 shrink-0 place-items-center border border-line font-mono text-zinc-400">{user.username.slice(0, 1).toUpperCase()}</span><span className="min-w-0 truncate text-zinc-500" title={user.email}>{user.email}</span></div>
        </div>
      </aside>
      <main className="min-w-0 px-5 pb-10 sm:px-8 lg:px-12">
        <header className="flex min-h-16 items-center justify-between gap-3 border-b border-line">
          <span id="new-document-heading" tabIndex={-1} className="text-sm text-zinc-400">{t('Không gian tài liệu')}</span>
          <WorkspaceNavigation><button className={ui('btn')} disabled={busy} onClick={logout}>{t('Đăng xuất')}</button></WorkspaceNavigation>
        </header>
        {error && <p role="alert" className={ui('error-box')}>{error}</p>}
        {destinationId != null && <div className="mt-5 flex min-w-0 items-center justify-between gap-3 border-b border-line pb-4 text-sm text-zinc-400"><span className="min-w-0 break-words"><Folder size={16} className="mr-2 inline text-orange-400"/>{currentFolder?.name || t('thư mục đang chọn')}</span><button type="button" className={ui('btn shrink-0')} onClick={() => openFolder('')}>{t('Ra ngoài thư mục')}</button></div>}
        {!folderReady && <p role="alert" className={ui('error-box')}>{folderState.loading ? t('Đang kiểm tra thư mục trước khi tải lên…') : t('Không thể dùng thư mục này. Chọn thư mục khác hoặc ra ngoài thư mục.')}</p>}
        <DocumentUpload compact folderId={destinationId} folderName={currentFolder?.name} folderReady={folderReady}/>
      </main>
    </div>
  </>;
}
