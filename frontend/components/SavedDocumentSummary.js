import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { useEffect, useState } from 'react';
import AnalysisResults from './AnalysisResults';

export default function SavedDocumentSummary({ documentId, jobId, readerVersion }) {
  const { t, locale, errorText } = useI18n();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setResult(null); setLoading(true); setError('');
    async function load() {
      try {
        const params = new URLSearchParams();
        if (jobId) params.set('job_id', jobId);
        const response = await fetch(`/api/documents/${documentId}/summary?${params}`, { signal: controller.signal, cache: 'no-store' });
        if (response.status === 401) { window.location.assign('/'); return; }
        if (!response.ok) throw new Error();
        const saved = await response.json();
        if (saved.document && (saved.document.document_id !== Number(documentId) || saved.document.schema_version !== 1)) throw new Error();
        if (!controller.signal.aborted) { setResult(saved); }
      } catch (err) {
        if (!controller.signal.aborted) setError(t("Không thể tải bản tóm tắt đã lưu. Vui lòng thử lại."));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [documentId, jobId, attempt]);
  const pending = loading;
  const stale = result?.document?.reader?.version !== readerVersion;
  return <section className={ui('reader-saved-summary')} aria-label={t("Bản tóm tắt đã lưu")} aria-busy={pending}>
    <h2>{t("Bản tóm tắt đã lưu")}</h2>
    <p className={ui('search-help')}>{t("Nội dung của toàn bộ tài liệu từ lần phân tích trước.")}</p>
    {pending && <p role="status">{t("Đang tải bản tóm tắt…")}</p>}
    {error && <div role="alert"><p className={ui('error-box')}>{errorText(error)}</p><button className={ui('btn')} onClick={() => setAttempt(value => value + 1)}>{t("Thử lại bản tóm tắt")}</button></div>}
    {!pending && !error && !result?.document && <p role="status">{t("Tài liệu chưa có bản tóm tắt đã lưu")}{jobId ? t(" trong tác vụ này") : ''}.</p>}
    {!pending && !error && result?.document && <>
      {stale ? <p className={ui('analysis-warning')} role="status">{t("Bản tóm tắt thuộc phiên bản tài liệu khác. Mở tác vụ cũ để xem kết quả.")}</p>
        : <AnalysisResults title="" data={{ documents: { [documentId]: result.document } }} mode={result.mode} jobId={result.job_id}/>}
      <a className={ui('btn')} href={`/results/${result.job_id}`}>{t("Xem tác vụ #")}{result.job_id}</a>
    </>}
  </section>;
}
