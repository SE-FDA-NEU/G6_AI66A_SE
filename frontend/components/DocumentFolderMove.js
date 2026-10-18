import { useEffect, useState } from 'react';

export default function DocumentFolderMove({ document, folders, foldersUnavailable, onMoved }) {
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
      setError('Không thể chuyển tài liệu. Lựa chọn được giữ lại; vui lòng thử lại.');
    } finally { setPending(false); }
  }

  const unknownFolder = document.folder_id != null && !folders.some(folder => folder.id === document.folder_id);
  return (
    <form className="document-folder-move" aria-label={`Sắp xếp ${document.original_filename}`} aria-busy={pending}
      onSubmit={event => { event.preventDefault(); move(target ? Number(target) : null); }}>
      <div className="folder-destination">
        <label htmlFor={`move-folder-${document.id}`}>Chuyển tài liệu tới</label>
        <select id={`move-folder-${document.id}`} value={target} disabled={pending || foldersUnavailable} onChange={event => setTarget(event.target.value)}>
          <option value="">Chưa phân thư mục</option>
          {unknownFolder && <option value={document.folder_id} disabled>Thư mục hiện tại (#{document.folder_id})</option>}
          {folders.map(folder => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
        </select>
      </div>
      <div className="folder-move-buttons">
        <button className="btn" disabled={pending || foldersUnavailable || target === String(document.folder_id ?? '')}>
          {pending ? 'Đang chuyển…' : 'Chuyển'}
        </button>
        {document.folder_id != null && <button type="button" className="btn" disabled={pending} onClick={() => move(null)}>Bỏ thư mục</button>}
      </div>
      {pending && <p role="status">Đang cập nhật thư mục…</p>}
      {error && <p role="alert" className="error-box">{error}</p>}
    </form>
  );
}
