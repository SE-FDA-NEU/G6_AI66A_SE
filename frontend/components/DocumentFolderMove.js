import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { useEffect, useState } from 'react';

export default function DocumentFolderMove({ document, folders, foldersUnavailable, onMoved, onCreateFolder }) {
  const { t, locale, errorText } = useI18n();
  const [target, setTarget] = useState(String(document.folder_id ?? ''));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setTarget(String(document.folder_id ?? '')); }, [document.folder_id]);

  async function move(folderId) {
    if (pending || folderId === document.folder_id || (folderId === null && document.folder_id == null)) return;
    setPending(true); setError('');
    try {
      const response = await fetch(`/api/documents/${document.id}/folder`, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ folder_id: folderId }) });
      if (response.status === 401) { window.location.assign('/'); return; }
      if (!response.ok) throw new Error();
      const updated = await response.json();
      if (updated.id !== document.id || updated.folder_id !== folderId) throw new Error();
      onMoved(updated);
    } catch {
      setError(t("Không thể chuyển tài liệu. Lựa chọn được giữ lại; vui lòng thử lại."));
    } finally { setPending(false); }
  }

  const unknownFolder = document.folder_id != null && !folders.some(folder => folder.id === document.folder_id);
  if (!foldersUnavailable && folders.length === 0 && document.folder_id == null) return <div className="space-y-2 border-t border-line pt-3 text-xs text-zinc-400">
    <p>{t('Tạo một thư mục trước khi thêm tài liệu vào.')}</p>
    {onCreateFolder ? <button type="button" className={ui('btn')} onClick={onCreateFolder}>{t('Tạo thư mục')}</button> : <a className={ui('btn')} href="/workspace#folder-name">{t('Tạo thư mục')}</a>}
  </div>;
  return (
    <form className={ui('document-folder-move')} aria-label={t("Sắp xếp {0}", document.original_filename)} aria-busy={pending}
      onSubmit={event => { event.preventDefault(); move(target ? Number(target) : null); }}>
      <div className={ui('folder-destination')}>
        <label htmlFor={`move-folder-${document.id}`}>{t("Chuyển tài liệu tới")}</label>
        <select id={`move-folder-${document.id}`} value={target} disabled={pending || foldersUnavailable} onChange={event => setTarget(event.target.value)}>
          <option value="">{t("Chưa phân thư mục")}</option>
          {unknownFolder && <option value={document.folder_id} disabled>{t("Thư mục hiện tại (#")}{document.folder_id})</option>}
          {folders.map(folder => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
        </select>
      </div>
      <div className={ui('folder-move-buttons')}>
        <button className={ui('btn')} disabled={pending || foldersUnavailable || target === String(document.folder_id ?? '')}>
          {pending ? t("Đang chuyển…") : t("Chuyển")}
        </button>
        {document.folder_id != null && <button type="button" className={ui('btn')} disabled={pending} onClick={() => move(null)}>{t("Bỏ thư mục")}</button>}
      </div>
      {pending && <p role="status">{t("Đang cập nhật thư mục…")}</p>}
      {error && <p role="alert" className={ui('error-box')}>{errorText(error)}</p>}
    </form>
  );
}
