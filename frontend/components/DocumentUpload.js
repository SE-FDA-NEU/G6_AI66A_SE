import BeginnerGuide from './BeginnerGuide';
import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { useEffect, useRef, useState } from 'react';
import { MB, validateSelection } from '../lib/upload-validation';
import UploadModeSelector, { UPLOAD_MODES } from './UploadModeSelector';

import { FileUp, Sparkles } from 'lucide-react';

export default function DocumentUpload({ compact = false, folderId = null, folderName = '', folderReady = true }) {
  const { t, locale, errorText } = useI18n();
  const [entries, setEntries] = useState([]);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState('bullet');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem('upload_analysis_mode');
      if (UPLOAD_MODES.some(option => option.value === saved)) {
        setMode(saved);
      }
    } catch {}
    setReady(true);
  }, []);
  const nextId = useRef(0);
  const picker = useRef(null);

  function handleModeChange(newMode) {
    setMode(newMode);
    try {
      sessionStorage.setItem('upload_analysis_mode', newMode);
    } catch {}
  }
  const accepted = entries.filter(entry => entry.errors.length === 0);
  const rejected = entries.length - accepted.length;
  const total = accepted.reduce((sum, entry) => sum + entry.file.size, 0);

  function addFiles(files) {
    if (submitting) return;
    const additions = Array.from(files, file => ({ id: nextId.current++, file }));
    setEntries(previous => {
      // Keep accepted files first so new/rejected files cannot displace them.
      const valid = previous.filter(entry => entry.errors.length === 0);
      const invalid = previous.filter(entry => entry.errors.length > 0);
      return validateSelection([...valid, ...invalid, ...additions]);
    });
  }

  function removeFile(id) {
    if (submitting) return;
    setEntries(previous => {
      const remaining = previous.filter(entry => entry.id !== id);
      return validateSelection([
        ...remaining.filter(entry => entry.errors.length === 0),
        ...remaining.filter(entry => entry.errors.length > 0),
      ]);
    });
  }

  async function submit() {
    if (!ready || submitting || !accepted.length || rejected || !folderReady) return;
    setSubmitting(true);
    setError('');
    const body = new FormData();
    accepted.forEach(entry => body.append('files', entry.file));
    body.append('mode', mode);
    body.append('language', locale);
    if (folderId != null) body.append('folder_id', String(folderId));
    try {
      const response = await fetch('/api/upload', { method: 'POST', credentials: 'same-origin', body });
      if (response.status === 401) { window.location.assign('/'); return; }
      if (folderId != null && (response.status === 403 || response.status === 404)) {
        setError(t('Thư mục không còn khả dụng. Chọn thư mục khác hoặc ra ngoài thư mục rồi thử lại.'));
        setSubmitting(false);
        return;
      }
      if (!response.ok) throw new Error('Upload failed');
      const result = await response.json();
      if (!/^[1-9]\d*$/.test(String(result.jobId))) throw new Error('Invalid job');
      window.location.assign(`/results/${result.jobId}`);
    } catch {
      setError(t("Không thể gửi tài liệu. Kiểm tra kết nối và thử lại."));
      setSubmitting(false);
    }
  }

  return (
      <section className={compact ? 'mx-auto w-full max-w-3xl space-y-6 py-10 sm:py-16' : ui('upload-content')}>
        {compact ? <div className="space-y-4 text-center">
          <div className="mx-auto mb-7 grid size-14 place-items-center border border-line bg-surface text-orange-400"><Sparkles size={26} strokeWidth={1.4}/></div>
          <p className="font-mono text-[10px] tracking-[.18em] text-zinc-500">DOCUMIND / {t('Một tài liệu. Nhiều điều sáng tỏ.')}</p>
          <h1 className="text-3xl leading-tight sm:text-5xl">{t('Bạn muốn khám phá điều gì?')}</h1>
          <p className="mx-auto max-w-lg text-sm leading-7 text-zinc-400">{t('Thêm tài liệu của bạn. Nhận bản tóm tắt dễ hiểu, rồi kiểm tra từng ý ngay trong nguồn.')}</p>
        </div> : <>
        <p className={ui('eyebrow')}>02 // DOCUMENT_INGEST</p>
        <h1>{t("Tải tài liệu")}</h1>
        <p className={ui('muted')}>{t("Chọn tài liệu để kiểm tra trước khi tải lên.")}</p>
        <p className={ui('search-help')}>{t("Bản tóm tắt sẽ được tạo và lưu bằng ngôn ngữ đang chọn.")}</p>
        </>}
        {compact && <p className="border-l-2 border-orange-500 bg-surface px-4 py-3 text-sm leading-6 text-zinc-400" role="status">
          {folderId != null ? t('Tài liệu mới sẽ được lưu vào “{0}”.', folderName || t('thư mục đang chọn')) : t('Tài liệu mới sẽ nằm ngoài thư mục.')}
        </p>}
        <div className={compact ? 'upload-picker space-y-4 border border-dashed border-zinc-600 bg-surface p-6 text-center transition-colors hover:border-zinc-400 sm:p-9' : ui('upload-picker')} onDragOver={event => event.preventDefault()}
          onDrop={event => { event.preventDefault(); addFiles(event.dataTransfer.files); }}>
          {compact ? <FileUp size={28} strokeWidth={1.3} className="mx-auto text-zinc-400"/> :
          <p className="font-mono text-[10px] tracking-widest text-zinc-500">01 // {t('Chọn tệp')}</p>
          }
          <h2>{t("Chọn hoặc kéo thả tệp vào đây")}</h2>
          <p id="upload-rules" className={compact ? 'text-xs leading-6 text-zinc-500' : undefined}>{t("PDF, DOCX hoặc PPTX · Tối đa 5 tệp · Mỗi tệp ≤ 5 MB · Tổng ≤ 50 MB")}</p>
          <label htmlFor="upload-files" className={compact ? 'sr-only' : undefined}>{t("Chọn tệp tài liệu")}</label>
          {compact && <button type="button" className={ui('btn primary')} disabled={!ready || submitting} onClick={() => picker.current?.click()}><FileUp size={16}/>{t('Chọn tệp tài liệu')}</button>}
          <input ref={picker} id="upload-files" className={compact ? 'sr-only' : undefined} aria-hidden={compact || undefined} tabIndex={compact ? -1 : undefined} type="file" multiple accept=".pdf,.docx,.pptx" disabled={!ready || submitting}
            aria-describedby="upload-rules" onChange={event => {
              addFiles(event.target.files);
              event.target.value = '';
            }} />
        </div>
        {(!compact || entries.length > 0) && <div role="status" className={ui('upload-summary')}>
          {accepted.length}{t("/5 tệp hợp lệ ·") + " "}{(total / MB).toFixed(2)}{" " + t("MB")}{rejected > 0 && <span> · {rejected}{" " + t("tệp cần kiểm tra")}</span>}
        </div>}
        {entries.length > 0 && <ul className={ui('upload-files')} aria-label={t("Tệp đã chọn")}>
          {entries.map(entry => <li key={entry.id} className={ui('upload-file')}>
            <div className={ui('upload-file-info')}>
              <strong>{entry.file.name}</strong>
              <span className={ui('upload-size')}>{(entry.file.size / MB).toFixed(2)}{" " + t("MB")}</span>
              {entry.errors.length > 0
                ? <div role="alert" className={ui('upload-errors')}>{entry.errors.map(error =>
                  <span className={ui('upload-error-badge')} key={error}>{t(error)}</span>)}</div>
                : <span className={ui('badge')}>{t("Hợp lệ")}</span>}
            </div>
            <button type="button" className={ui('btn')} disabled={submitting} aria-label={t("Xóa {0}", entry.file.name)}
              onClick={() => removeFile(entry.id)}>{t("Xóa")}</button>
          </li>)}
        </ul>}
        {accepted.length > 0 && rejected === 0 && <p className={ui('upload-ready')}>{t("Các tệp đã chọn hợp lệ và sẵn sàng tải lên.")}</p>}
        <div className={ui('analysis-submit')}>
          {!compact && <><BeginnerGuide context="upload" />
          <p className="font-mono text-[10px] tracking-widest text-zinc-500">02 // {t('Chọn kiểu phân tích')}</p></>}
          <UploadModeSelector value={mode} disabled={!ready || submitting} onChange={handleModeChange} variant={compact ? 'cards' : 'select'} />
          <button type="button" className={ui(compact ? 'btn primary w-full' : 'btn primary')} disabled={!ready || submitting || !accepted.length || rejected > 0 || !folderReady}
            onClick={submit}>{submitting ? t("Đang gửi…") : t("Tải lên và phân tích")}</button>
          {error && <p className={ui('error-box')} role="alert">{errorText(error)}</p>}
        </div>
        {compact && <p className="text-center text-xs leading-6 text-zinc-500">{t('Mở lại bản tóm tắt từ lịch sử bên trái bất cứ lúc nào.')}</p>}
      </section>
  );
}
