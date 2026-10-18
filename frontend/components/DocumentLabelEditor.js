import { useI18n } from '../lib/i18n';
import { useEffect, useRef, useState } from 'react';

export default function DocumentLabelEditor({ documentId, document, onSaved, onUnavailable }) {
  const { t, locale, errorText } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const activeRequest = useRef(null);
  useEffect(() => () => activeRequest.current?.abort(), [documentId]);

  async function save(payload) {
    if (activeRequest.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    setPending(true); setError(''); setMessage('');
    try {
      const response = await fetch(`/api/documents/${documentId}/label`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: controller.signal,
      });
      if (response.status === 401) { window.location.assign('/'); return; }
      if (response.status === 410) { onUnavailable?.(); throw new Error('source_expired'); }
      if (!response.ok) throw new Error();
      const saved = await response.json();
      if (saved.id !== Number(documentId) || saved.review_state !== 'confirmed' || !saved.user_label) throw new Error();
      if (controller.signal.aborted) return;
      setEditing(false); setMessage(t("Đã lưu nhãn người dùng."));
      onSaved(saved);
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message === 'source_expired'
        ? t("Nguồn đã hết hạn và không còn khả dụng. Không thể cập nhật nhãn.")
        : t("Không thể lưu nhãn. Nội dung đã nhập được giữ lại; vui lòng thử lại."));
    } finally {
      if (!controller.signal.aborted) setPending(false);
      activeRequest.current = null;
    }
  }

  function beginEdit() {
    setDraft(document.user_label ?? document.ai_label ?? '');
    setError(''); setMessage(''); setEditing(true);
  }

  const canConfirm = document.review_state !== 'confirmed' || !document.user_label;
  return (
    <section className="document-label-editor" data-testid="document-label-editor" aria-label={t("Xác nhận và chỉnh sửa nhãn")} aria-busy={pending}>
      {editing ? <form onSubmit={event => { event.preventDefault(); if (draft.trim()) save({ user_label: draft.trim(), review_state: 'confirmed' }); }}>
        <label htmlFor={`user-label-${documentId}`}>{t("Nhãn người dùng")}</label>
        <div className="label-editor-controls">
          <input id={`user-label-${documentId}`} value={draft} required maxLength={100} disabled={pending}
            onChange={event => setDraft(event.target.value)} />
          <button className="btn" disabled={pending || !draft.trim()}>{pending ? t("Đang lưu…") : t("Lưu nhãn")}</button>
          <button type="button" className="btn" disabled={pending} onClick={() => { setEditing(false); setError(''); }}>{t("Hủy chỉnh sửa")}</button>
        </div>
      </form> : <div className="label-editor-controls">
        {canConfirm && (document.user_label || document.ai_label) && <button className="btn" disabled={pending}
          onClick={() => save({ review_state: 'confirmed' })}>
          {pending ? t("Đang lưu…") : document.user_label ? t("Xác nhận nhãn người dùng") : t("Xác nhận nhãn AI")}
        </button>}
        <button className="btn" disabled={pending} onClick={beginEdit}>{t("Chỉnh sửa nhãn")}</button>
      </div>}
      {pending && <p role="status">{t("Đang lưu nhãn người dùng…")}</p>}
      {error && <p className="error-box" role="alert">{errorText(error)}</p>}
      {message && <p role="status">{t(message)}</p>}
    </section>
  );
}
