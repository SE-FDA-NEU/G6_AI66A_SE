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
  const [geminiKey, setGeminiKey] = useState('');
  const [savedKey, setSavedKey] = useState(false);
  const [keyBusy, setKeyBusy] = useState(false);
  const [keyError, setKeyError] = useState('');
  const keyRevision = useRef(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const revision = keyRevision.current;
    fetch('/auth/gemini-key', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error();
        const result = await response.json();
        if (revision === keyRevision.current) setSavedKey(result.configured === true);
      }).catch(error => {
        if (error.name !== 'AbortError' && revision === keyRevision.current) setKeyError(t('Could not load the saved API key. Please retry.'));
      });
    return () => controller.abort();
  }, [t]);
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

  async function saveKey() {
    const response = await fetch('/auth/gemini-key', { method: 'PUT', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key: geminiKey.trim() }) });
    if (!response.ok) throw new Error('Could not save the API key. Please retry.');
    keyRevision.current++;
    setSavedKey(true);
    setGeminiKey('');
    setKeyError('');
  }

  async function updateKey(remove = false) {
    setKeyBusy(true);
    setKeyError('');
    try {
      if (remove) {
        const response = await fetch('/auth/gemini-key', { method: 'DELETE', credentials: 'same-origin' });
        if (!response.ok) throw new Error();
        keyRevision.current++;
        setSavedKey(false);
        setGeminiKey('');
      } else {
        await saveKey();
      }
    } catch {
      setKeyError(t(remove ? 'Could not remove the API key. Please retry.' : 'Could not save the API key. Please retry.'));
    } finally { setKeyBusy(false); }
  }

  async function submit() {
    if (!ready || submitting || keyBusy || !accepted.length || rejected || !folderReady || (!geminiKey.trim() && !savedKey)) return;
    setSubmitting(true);
    setError('');
    const body = new FormData();
    accepted.forEach(entry => body.append('files', entry.file));
    body.append('mode', mode);
    body.append('language', locale);
    if (folderId != null) body.append('folder_id', String(folderId));
    try {
      // Save first, then use this exact replacement for the current batch.
      const enteredKey = geminiKey.trim();
      if (enteredKey) {
        try { await saveKey(); }
        catch { setError(t('Could not save the API key. Please retry.')); setSubmitting(false); return; }
      }
      const response = await fetch('/api/upload', { method: 'POST', credentials: 'same-origin',
        headers: enteredKey ? { 'X-Gemini-Api-Key': enteredKey } : {}, body });
      if (response.status === 401) { window.location.assign('/'); return; }
      if (folderId != null && (response.status === 403 || response.status === 404)) {
        setError(t('Thư mục không còn khả dụng. Chọn thư mục khác hoặc ra ngoài thư mục rồi thử lại.'));
        setSubmitting(false);
        return;
      }
      if (response.status === 400 || response.status === 409) {
        setSavedKey(false);
        setError(t(response.status === 409 ? 'Saved Gemini API key could not be read. Please replace it.' : 'Enter your Gemini API key to analyze documents.'));
        setSubmitting(false);
        return;
      }
      if (!response.ok) throw new Error('Upload failed');
      const result = await response.json();
      if (!/^[1-9]\d*$/.test(String(result.jobId))) throw new Error('Invalid job');
      setGeminiKey('');
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
          <div className="space-y-2 text-left">
            <label htmlFor="gemini-api-key" className="block text-sm">{t('Your Gemini API key')}</label>
            {savedKey && <p className="text-xs text-zinc-400" aria-live="polite">{t('An API key is saved to your account. Leave this field empty to use it, or enter a replacement.')}</p>}
            <input id="gemini-api-key" type="password" autoComplete="off" spellCheck={false}
              maxLength={256} value={geminiKey} disabled={!ready || submitting || keyBusy}
              aria-describedby="gemini-key-help" placeholder="AIza…"
              className="w-full rounded border border-zinc-600 bg-surface px-3 py-2 text-sm"
              onChange={event => setGeminiKey(event.target.value)} />
            <p id="gemini-key-help" className="text-xs leading-6 text-zinc-400">
              {t('Your key is saved encrypted to your account and reused for future uploads. A replacement overwrites the saved key. Gemini quota applies to your key.')}{' '}
              <a href="https://aistudio.google.com/api-keys" target="_blank" rel="noopener noreferrer" className="underline">{t('Get a Gemini API key')}</a>
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={ui('btn')} disabled={!ready || submitting || keyBusy || !geminiKey.trim()}
                onClick={() => updateKey()}>{t(savedKey ? 'Change API key' : 'Save API key')}</button>
              {savedKey && <button type="button" className={ui('btn')} disabled={submitting || keyBusy}
                onClick={() => updateKey(true)}>{t('Remove saved key')}</button>}
            </div>
            {keyError && <p role="alert" className={ui('error-box')}>{t(keyError)}</p>}
          </div>
          <button type="button" className={ui(compact ? 'btn primary w-full' : 'btn primary')} disabled={!ready || submitting || keyBusy || !accepted.length || rejected > 0 || !folderReady || (!geminiKey.trim() && !savedKey)}
            onClick={submit}>{submitting ? t("Đang gửi…") : t("Tải lên và phân tích")}</button>
          {error && <p className={ui('error-box')} role="alert">{errorText(error)}</p>}
        </div>
        {compact && <p className="text-center text-xs leading-6 text-zinc-500">{t('Mở lại bản tóm tắt từ lịch sử bên trái bất cứ lúc nào.')}</p>}
      </section>
  );
}
