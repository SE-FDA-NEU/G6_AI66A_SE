import { useI18n } from '../lib/i18n';
import { useState } from 'react';
import WorkspaceIcon from './WorkspaceIcon';

export default function WorkspaceFolders({ folders, loading, error, reload, add, selected, onSelect }) {
  const { t, locale, errorText } = useI18n();
  const [name, setName] = useState('');
  const [pending, setPending] = useState(false);
  const [createError, setCreateError] = useState('');
  const [message, setMessage] = useState('');

  async function create(event) {
    event.preventDefault();
    if (pending || !name.trim()) return;
    setPending(true); setCreateError(''); setMessage('');
    try {
      const response = await fetch('/api/folders', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }) });
      if (response.status === 401) { window.location.assign('/'); return; }
      if (!response.ok) throw new Error();
      const folder = await response.json();
      if (!Number.isSafeInteger(folder.id) || typeof folder.name !== 'string') throw new Error();
      add(folder); setName(''); setMessage(t("Đã tạo thư mục “{0}”.", folder.name));
    } catch {
      setCreateError(t("Không thể tạo thư mục. Tên đã nhập được giữ lại; vui lòng thử lại."));
    } finally { setPending(false); }
  }

  return (
    <section className="workspace-folders" aria-label={t("Quản lý thư mục")}>
      <div className="section-heading"><div><h2>{t("Thư mục của bạn") + " "}<span className="item-count">{folders.length}</span></h2><p className="search-help">{t("Bấm vào thư mục để xem các tài liệu bên trong.")}</p></div></div>
      {loading && <p role="status">{t("Đang tải thư mục…")}</p>}
      {error && <div role="alert"><p className="error-box">{errorText(error)}</p><button className="btn" onClick={reload}>{t("Thử lại thư mục")}</button></div>}
      {!loading && !error && folders.length === 0 && <p className="search-help">{t("Chưa có thư mục. Tạo thư mục để sắp xếp tài liệu.")}</p>}
      <div className="folder-location"><label htmlFor="workspace-folder-select">{t("Thư mục hiển thị")}</label>
      <select id="workspace-folder-select" value={selected} disabled={loading || Boolean(error)} onChange={event => onSelect(event.target.value)}>
        <option value="">{t("Tất cả tài liệu")}</option><option value="unassigned">{t("Chưa phân thư mục")}</option>
        {folders.map(folder => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
      </select></div>
      {!selected && !loading && !error && <div className="folder-grid" aria-label={t("Các thư mục")}>
        {folders.map(folder => <button className="folder-tile" key={folder.id} onClick={() => onSelect(String(folder.id))} aria-label={t("Mở thư mục {0}", folder.name)}>
          <span className="folder-tile-icon"><WorkspaceIcon name="folder" size={38} /></span>
          <strong>{folder.name}</strong><span className="folder-tile-hint">{t("Mở thư mục") + " "}<WorkspaceIcon name="chevron" size={14}/></span>
        </button>)}
      </div>}
      <form className="folder-create-form" onSubmit={create} aria-label={t("Tạo thư mục")}>
        <label htmlFor="folder-name">{t("Tên thư mục mới")}</label>
        <div className="folder-create-controls">
          <input id="folder-name" value={name} maxLength={100} required disabled={pending}
            placeholder={t("Ví dụ: Research")} onChange={event => setName(event.target.value)} />
          <button className="btn" disabled={pending || loading || Boolean(error) || !name.trim()}>{pending ? t("Đang tạo…") : t("Tạo thư mục")}</button>
        </div>
      </form>
      {createError && <p className="error-box" role="alert">{errorText(createError)}</p>}
      {message && <p role="status">{t(message)}</p>}
    </section>
  );
}
