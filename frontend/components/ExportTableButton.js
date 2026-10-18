import { languageHeaders, useI18n } from '../lib/i18n';
import { useEffect, useRef, useState } from 'react';

function hasCompleteTable(job) {
  // UI readiness only; the export API independently validates the full saved
  // contract, every file's completion and ownership before returning a PDF.
  const files = job?.job_files || [];
  const rows = job?.result_data?.documents || {};
  return job?.mode === 'table' && job.status === 'completed' &&
    job.file_count >= 1 && job.file_count <= 5 && job.completed_count === job.file_count &&
    files.length === job.file_count && new Set(files.map(file => file.document_id)).size === files.length &&
    job.result_data?.schema_version === 1 && Object.keys(rows).length === files.length &&
    files.every(file => {
      const row = rows[file.document_id];
      return file.status === 'completed' && row?.schema_version === 1 &&
        row.document_id === file.document_id && row.mode === 'table' &&
        row.analysis_status === 'completed' && row.output?.type === 'table' &&
        ['value', 'payment_term', 'penalty'].every(field =>
          row.output[field] && typeof row.output[field] === 'object');
    });
}

export default function ExportTableButton({ job, jobId }) {
  const { t, locale, errorText } = useI18n();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [downloaded, setDownloaded] = useState(false);
  const request = useRef(null);
  const downloadUrl = useRef(null);
  const revokeTimer = useRef(null);
  const ready = hasCompleteTable(job);

  useEffect(() => {
    setPending(false);
    setError('');
    setDownloaded(false);
    return () => {
      request.current?.abort();
      request.current = null;
      clearTimeout(revokeTimer.current);
      if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
      downloadUrl.current = null;
    };
  }, [jobId, locale]);

  async function download() {
    if (!ready || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setError('');
    setDownloaded(false);
    try {
      const response = await fetch(`/jobs/${jobId}/export.pdf`, {
        credentials: 'same-origin', cache: 'no-store', signal: controller.signal, headers: languageHeaders(locale),
      });
      if (response.status === 401) throw new Error(t("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để xuất PDF."));
      if (response.status === 403 || response.status === 404) throw new Error(t("Không tìm thấy tác vụ hoặc bạn không có quyền xuất bảng này."));
      if (response.status === 409) throw new Error(t("Bảng chưa sẵn sàng để xuất PDF. Vui lòng tải lại trang để cập nhật kết quả."));
      if (!response.ok) throw new Error(t("Không thể xuất PDF. Vui lòng thử lại."));
      if (response.headers.get('content-type')?.split(';')[0].trim() !== 'application/pdf') {
        throw new Error(t("Máy chủ không trả về PDF hợp lệ. Vui lòng thử lại."));
      }
      const blob = await response.blob();
      if (await blob.slice(0, 5).text() !== '%PDF-') {
        throw new Error(t("Máy chủ không trả về PDF hợp lệ. Vui lòng thử lại."));
      }
      if (controller.signal.aborted) return;
      clearTimeout(revokeTimer.current);
      if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
      const url = URL.createObjectURL(blob);
      downloadUrl.current = url;
      const link = document.createElement('a');
      link.href = url;
      link.download = `comparison-${jobId}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Let the browser consume the download before releasing its blob URL.
      revokeTimer.current = setTimeout(() => {
        URL.revokeObjectURL(url);
        if (downloadUrl.current === url) downloadUrl.current = null;
      }, 30000);
      setDownloaded(true);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof TypeError
        ? t("Không thể kết nối để tải PDF. Vui lòng thử lại.") : err.message);
    } finally {
      if (request.current === controller) {
        request.current = null;
        setPending(false);
      }
    }
  }

  return <section className="table-export" aria-label={t("Xuất bảng so sánh")}>
    <button type="button" className="btn" onClick={download} disabled={!ready || pending}
      aria-busy={pending} aria-describedby="table-export-status">{t("Export Table")}</button>
    <p id="table-export-status" role="status" aria-live="polite" className="muted">
      {pending ? t("Đang tạo và tải PDF…") : !ready ? t("Chỉ xuất PDF khi tác vụ hoàn tất và có đủ tất cả dòng trong bảng.")
        : downloaded ? t("Đã gửi PDF để tải xuống.") : t("Tải bảng so sánh đã lưu dưới dạng PDF.")}
    </p>
    {error && <p className="error-box" role="alert">{errorText(error)}</p>}
  </section>;
}
