import { useState } from 'react';

export default function WorkspaceFolders({ folders, loading, error, reload, add, selected, onSelect }) {
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
      add(folder); setName(''); setMessage(`Đã tạo thư mục “${folder.name}”.`);
    } catch {
      setCreateError('Không thể tạo thư mục. Tên đã nhập được giữ lại; vui lòng thử lại.');
    } finally { setPending(false); }
  }

  return (
    <section className="workspace-folders" aria-label="Quản lý thư mục">
      <h2>Thư mục của bạn</h2>
      {loading && <p role="status">Đang tải thư mục…</p>}
      {error && <div role="alert"><p className="error-box">{error}</p><button className="btn" onClick={reload}>Thử lại thư mục</button></div>}
      {!loading && !error && folders.length === 0 && <p className="search-help">Chưa có thư mục. Tạo thư mục để sắp xếp tài liệu.</p>}
      <label htmlFor="workspace-folder-select">Thư mục hiển thị</label>
      <select id="workspace-folder-select" value={selected} disabled={loading || Boolean(error)} onChange={event => onSelect(event.target.value)}>
        <option value="">Tất cả tài liệu</option>
        {folders.map(folder => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
      </select>
      <form className="folder-create-form" onSubmit={create} aria-label="Tạo thư mục">
        <label htmlFor="folder-name">Tên thư mục mới</label>
        <div className="folder-create-controls">
          <input id="folder-name" value={name} maxLength={100} required disabled={pending}
            placeholder="Ví dụ: Research" onChange={event => setName(event.target.value)} />
          <button className="btn" disabled={pending || loading || Boolean(error) || !name.trim()}>{pending ? 'Đang tạo…' : 'Tạo thư mục'}</button>
        </div>
      </form>
      {createError && <p className="error-box" role="alert">{createError}</p>}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
