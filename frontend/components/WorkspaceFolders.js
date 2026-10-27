import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { useState } from 'react';

export default function WorkspaceFolders({ add }) {
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
    <section className={ui('workspace-folders')} aria-label={t("Tạo thư mục")}>
      <form className={ui('folder-create-form')} onSubmit={create} aria-label={t("Tạo thư mục")}>
        <label htmlFor="folder-name">{t("Tên thư mục mới")}</label>
        <div className={ui('folder-create-controls')}>
          <input id="folder-name" value={name} maxLength={100} required disabled={pending}
            placeholder={t("Ví dụ: Research")} onChange={event => setName(event.target.value)} />
          <button className={ui('btn')} disabled={pending || !name.trim()}>{pending ? t("Đang tạo…") : t("Tạo thư mục")}</button>
        </div>
      </form>
      {createError && <p className={ui('error-box')} role="alert">{errorText(createError)}</p>}
      {message && <p role="status">{t(message)}</p>}
    </section>
  );
}
