import { useI18n } from '../lib/i18n';
import { readLocale } from '../lib/i18n';
import Head from 'next/head';
import { useState } from 'react';
import { useRouter } from 'next/router';
import { getSession } from '../lib/session';
import WorkspaceSearch from '../components/WorkspaceSearch';
import WorkspaceDocumentList from '../components/WorkspaceDocumentList';
import WorkspaceNavigation from '../components/WorkspaceNavigation';
import WorkspaceFolders from '../components/WorkspaceFolders';
import useFolders from '../lib/use-folders';
import WorkspaceLabelFilter from '../components/WorkspaceLabelFilter';
import usePageRefresh from '../lib/use-page-refresh';
import WorkspaceIcon from '../components/WorkspaceIcon';

export default function Workspace({ user }) {
  const { t, locale, errorText } = useI18n();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [filename, setFilename] = useState('');
  const [filenameDraft, setFilenameDraft] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const folderState = useFolders();
  const router = useRouter();
  const requestedFolder = router.query.folder;
  const selectedFolder = typeof requestedFolder === 'string' && /^(unassigned|[1-9]\d*)$/.test(requestedFolder) ? requestedFolder : '';
  const [aiLabel, setAiLabel] = useState('');
  const [revision, setRevision] = useState(0);
  const [moveMessage, setMoveMessage] = useState('');
  const [labelMessage, setLabelMessage] = useState('');
  usePageRefresh(() => setRevision(value => value + 1));

  function labelSaved(document) {
    setLabelMessage(t("Đã lưu nhãn người dùng cho “{0}”.", document.original_filename));
    setRevision(value => value + 1);
  }

  function documentMoved(document) {
    const folder = folderState.folders.find(item => item.id === document.folder_id);
    setMoveMessage(t("Đã chuyển “{0}” {1}.", document.original_filename, document.folder_id == null ? t("về Chưa phân thư mục") : t("tới “{0}”", folder?.name || t("thư mục đã chọn"))));
    setRevision(value => value + 1);
  }

  const currentFolder = folderState.folders.find(folder => String(folder.id) === selectedFolder);
  const location = selectedFolder === 'unassigned' ? t("Chưa phân thư mục") : currentFolder?.name || t("Tất cả tài liệu");
  function openFolder(id) {
    router.push({ pathname: '/workspace', query: id ? { folder: id } : {} }, undefined, { shallow: true, scroll: false });
    setFilename(''); setFilenameDraft(''); setSidebarOpen(false);
  }

  async function logout() {
    setBusy(true);
    try {
      const response = await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) throw new Error();
      window.location.assign('/');
    } catch {
      setError(t("Không thể đăng xuất. Vui lòng thử lại."));
      setBusy(false);
    }
  }

  return (
    <>
      <Head>
        <title>{t("DocuMind · Không gian tài liệu")}</title>
      </Head>
      <div className="library-shell">
        <aside className="library-sidebar" data-open={sidebarOpen} aria-label={t("Thanh bên thư viện")}>
          <a href="/workspace" className="brand"><span className="brand-mark"><WorkspaceIcon name="file" size={23}/></span>{t("DocuMind")}<span className="brand-dot">.</span></a>
          <button className="btn sidebar-toggle" aria-expanded={sidebarOpen} aria-controls="library-sidebar-links" onClick={() => setSidebarOpen(!sidebarOpen)}>{sidebarOpen ? t("Đóng thư mục") : t("Mở thư mục")}</button>
          <div id="library-sidebar-links" className="sidebar-body">
            <p className="sidebar-caption">{t("KHÔNG GIAN LÀM VIỆC")}</p>
            <nav aria-label={t("Điều hướng thư viện")}>
              <button className={`sidebar-item ${!selectedFolder ? 'active' : ''}`} aria-current={!selectedFolder ? 'page' : undefined} onClick={() => openFolder('')}><WorkspaceIcon name="grid"/>{t("Tất cả tài liệu")}</button>
              <button className={`sidebar-item ${selectedFolder === 'unassigned' ? 'active' : ''}`} aria-current={selectedFolder === 'unassigned' ? 'page' : undefined} onClick={() => openFolder('unassigned')}><WorkspaceIcon name="inbox"/>{t("Chưa phân thư mục")}</button>
              <p className="sidebar-caption">{t("THƯ MỤC") + " "}<span>{folderState.folders.length}</span></p>
              {folderState.loading && <p className="search-help">{t("Đang tải…")}</p>}
              {folderState.error && <p className="search-help">{t("Chưa tải được thư mục. Thử lại ở khu vực chính.")}</p>}
              {folderState.folders.map(folder => <button key={folder.id} className={`sidebar-item ${selectedFolder === String(folder.id) ? 'active' : ''}`} aria-current={selectedFolder === String(folder.id) ? 'page' : undefined} onClick={() => openFolder(String(folder.id))}><WorkspaceIcon name="folder"/><span>{folder.name}</span></button>)}
              {!folderState.loading && !folderState.error && !folderState.folders.length && <p className="search-help">{t("Thư mục bạn tạo sẽ xuất hiện ở đây.")}</p>}
            </nav>
            <div className="sidebar-tip"><WorkspaceIcon name="folder"/><strong>{t("Mọi tài liệu, một nơi")}</strong><p>{t("Tạo thư mục, chuyển tệp vào và tìm lại khi cần.")}</p></div>
            <div className="sidebar-account"><span className="account-avatar">{user.username.slice(0, 1).toUpperCase()}</span><div><strong>{user.username}</strong><span>{user.email}</span></div></div>
          </div>
        </aside>
        <main className="workspace library-main">
          <header className="library-topbar">
            <span className="topbar-label"><WorkspaceIcon name="grid" size={18}/>{" " + t("Thư viện cá nhân")}</span>
            <WorkspaceNavigation><button className="btn" onClick={logout} disabled={busy}>{t("Đăng xuất")}</button></WorkspaceNavigation>
          </header>
          <section className="workspace-content">
            <div className="library-heading"><div><p className="eyebrow">{t("THƯ VIỆN CỦA BẠN")}</p><h1>{t("Không gian tài liệu")}</h1><p className="library-description">{t("Sắp xếp gọn gàng. Tìm lại dễ dàng.")}</p></div>
              <a className="btn primary upload-link" href="/upload"><WorkspaceIcon name="upload" size={19}/>{t("Tải tài liệu")}</a>
            </div>
            {error && <p role="alert" className="error-box">{errorText(error)}</p>}
            <nav className="library-breadcrumb" aria-label={t("Đường dẫn thư mục")}><button onClick={() => openFolder('')}><WorkspaceIcon name="grid" size={16}/>{t("Thư viện")}</button><WorkspaceIcon name="chevron" size={14}/><span aria-current="page">{location}</span></nav>
            <WorkspaceFolders {...folderState} selected={selectedFolder} onSelect={openFolder}/>
            {selectedFolder && <div className="open-folder-heading"><WorkspaceIcon name={selectedFolder === 'unassigned' ? 'inbox' : 'folder'} size={28}/><div><h2>{location}</h2><p className="search-help">{selectedFolder === 'unassigned' ? t("Các tệp chưa được xếp vào thư mục. Dùng “Chuyển tài liệu tới” trên thẻ để sắp xếp.") : t("Bạn đang xem các tài liệu trong thư mục này.")}</p></div></div>}
            {moveMessage && <p className="library-notice" role="status">{t(moveMessage)}</p>}
            {labelMessage && <p className="library-notice" role="status">{t(labelMessage)}</p>}
            <div className="library-tools">
              <div className="filename-search"><form role="search" aria-label={t("Tìm tên tệp trong danh sách")} onSubmit={event => { event.preventDefault(); setFilename(filenameDraft.trim()); }}>
                <label htmlFor="filename-search">{t("Tìm theo tên tệp")}</label><p className="search-help">{t("Tìm tên tệp trong") + " "}{location === t("Tất cả tài liệu") ? t("toàn bộ thư viện") : `“${location}”`}{t(", kể cả các trang danh sách khác.")}</p>
                <div className="search-bar"><input id="filename-search" type="search" maxLength={500} placeholder={t("Ví dụ: hợp đồng.pdf, báo cáo…")} value={filenameDraft} onChange={event => setFilenameDraft(event.target.value)}/><button className="btn" type="submit">{t("Tìm tệp")}</button>{filename && <button className="btn" type="button" onClick={() => { setFilename(''); setFilenameDraft(''); }}>{t("Xóa tên tệp")}</button>}</div>
              </form></div>
              <details className="library-disclosure"><summary><WorkspaceIcon name="search" size={18}/><span><strong>{t("Tìm trong nội dung tài liệu")}</strong><small>{t("Tìm đoạn văn, điều khoản hoặc ý chính và mở đúng trang nguồn")}</small></span></summary><WorkspaceSearch folders={folderState.folders} foldersUnavailable={folderState.loading || Boolean(folderState.error)} refreshKey={revision}/></details>
            </div>
            <details className="library-disclosure label-disclosure"><summary><WorkspaceIcon name="grid" size={16}/><span><strong>{t("Bộ lọc nhãn AI")}{aiLabel ? ` · ${aiLabel}` : ''}</strong><small>{t("Thu hẹp danh sách theo phân loại của AI")}</small></span></summary><WorkspaceLabelFilter label={aiLabel} folderName={location} hasFolder={Boolean(selectedFolder)} onApply={setAiLabel} onClear={() => setAiLabel('')} onClearAll={() => { setAiLabel(''); openFolder(''); }}/></details>
            <WorkspaceDocumentList key={JSON.stringify([selectedFolder, aiLabel, filename])} folderId={selectedFolder} filename={filename} aiLabel={aiLabel} folders={folderState.folders} foldersUnavailable={folderState.loading || Boolean(folderState.error)} refreshKey={revision} onMoved={documentMoved} onLabelSaved={labelSaved}/>
          </section>
        </main>
      </div>
    </>
  );
}

export async function getServerSideProps({ req, res }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  return user ? { props: { user, initialLocale: readLocale(req.headers.cookie) } } : { redirect: { destination: '/', permanent: false } };
}

