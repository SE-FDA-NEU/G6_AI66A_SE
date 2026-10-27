import WorkflowSteps from '../../components/WorkflowSteps';
import BeginnerGuide from '../../components/BeginnerGuide';
import { ui } from '../../lib/ui';
import { useI18n } from '../../lib/i18n';
import { readLocale } from '../../lib/i18n';
import Head from 'next/head';
import { useEffect, useState } from 'react';
import { getSession } from '../../lib/session';
import AnalysisResults from '../../components/AnalysisResults';
import WorkspaceNavigation from '../../components/WorkspaceNavigation';
import ExportTableButton from '../../components/ExportTableButton';
import usePageRefresh from '../../lib/use-page-refresh';

const labels = {
  pending: 'Pending', processing: 'Processing', completed: 'Completed',
  failed: 'Failed', timed_out: 'Timed out',
};
const terminal = new Set(['completed', 'failed', 'timed_out']);

function Badge({ status }) {
  const { t, locale, errorText } = useI18n();
  return <span className={ui(`job-badge job-${status}`)}>{t(labels[status] || 'Unknown')}</span>;
}

export default function Results({ jobId }) {
  const { t, locale, errorText } = useI18n();
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  usePageRefresh(() => setRevision(value => value + 1));

  useEffect(() => {
    let stopped = false;
    let timer;
    const controller = new AbortController();
    setJob(null);
    setError('');

    async function poll() {
      try {
        const response = await fetch(`/jobs/${jobId}`, {
          credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        });
        if (stopped) return;
        if (response.status === 401) {
          window.location.assign('/');
          return;
        }
        if (response.status === 403 || response.status === 404) {
          setJob(null);
          setError(t("Không tìm thấy tác vụ hoặc bạn không có quyền truy cập."));
          return;
        }
        if (response.status === 410) {
          setJob(null);
          setError(t("Nguồn đã hết hạn. Kết quả này không còn khả dụng."));
          return;
        }
        if (!response.ok) throw new Error('Cannot fetch job');
        const next = await response.json();
        if (next.job_files?.some(file => file.error_message?.includes('source_expired'))) next.result_data = null;
        if (stopped) return;
        setJob(next);
        setError('');
        if (terminal.has(next.status)) return;
      } catch (err) {
        if (stopped || err.name === 'AbortError') return;
        setError(t("Không thể cập nhật tiến độ. Hệ thống sẽ tự thử lại."));
      }
      if (!stopped) timer = setTimeout(poll, 3000);
    }

    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
      controller.abort();
    };
  }, [jobId, revision]);

  const total = job?.file_count || 0;
  const completed = Math.min(total, Math.max(0, job?.completed_count || 0));

  return <>
    <Head><title>{t("DocuMind · Tiến độ xử lý")}</title></Head>
    <main className={ui('workspace results-page')}>
      <header><a href="/workspace" className={ui('brand')}>{t("DocuMind")}<span className={ui('brand-dot')}>.</span></a>
        <WorkspaceNavigation><a className={ui('btn')} href="/workspace">{t("Về không gian tài liệu")}</a></WorkspaceNavigation></header>
      <WorkflowSteps step={3}/>
      <section id="results" className={ui('results-content')}>
        <p className={ui('eyebrow')}>{t("TÁC VỤ #")}{jobId}</p>
        <h1>{t("Tiến độ xử lý")}</h1>
        <BeginnerGuide context="results" />
        <div className="flex flex-wrap gap-2">
          {Object.keys(job?.result_data?.documents || {}).length > 0 && <a href="#analysis-output" className={ui('btn primary')}>{t('Đọc kết quả')} ↓</a>}
          <a href="/upload" className={ui('btn')}>{t('Tải thêm tài liệu')}</a>
        </div>
        {!job && !error && <p role="status">{t("Đang tải tiến độ…")}</p>}
        {error && <p className={ui('error-box')} role="alert">{errorText(error)}</p>}
        {error && <button className={ui('btn')} onClick={() => setRevision(value => value + 1)}>{t("Thử lại bản tóm tắt")}</button>}
        {job && <>
          <section className={ui('job-progress-card')} aria-label={t("Tiến độ tác vụ")}>
            <div className={ui('job-progress-heading')}><h2>{t("Trạng thái xử lý")}</h2>
              <span aria-label={t("Trạng thái job")} role="status"><Badge status={job.status} /></span></div>
            <p className={ui('job-count')} aria-live="polite">{completed}/{total}{" " + t("tệp đã xử lý thành công")}</p>
            <progress aria-label={t("Tiến độ xử lý")} max={total || 1} value={completed}
              aria-valuetext={t("{0}/{1} tệp đã xử lý thành công", completed, total)} />
            <p className={ui('job-progress-note')}>{job.status === 'completed'
              ? t("Tất cả tài liệu đã được xử lý xong.")
              : job.status === 'failed' ? t("Tác vụ kết thúc với lỗi. Xem chi tiết từng tệp bên dưới.")
              : job.status === 'timed_out' ? t("Tác vụ đã vượt quá thời gian xử lý cho phép.")
              : t("Tiến độ tự cập nhật mỗi 3 giây. Bạn có thể quay lại trang này sau.")}</p>
          </section>
          <h2 className={ui('job-files-heading')}>{t("Trạng thái từng tệp")}</h2>
          {job.job_files?.some(file => file.error_message?.includes('source_expired')) && <p className={ui('error-box')} role="alert">{t("Nguồn đã hết hạn và không còn khả dụng. Kết quả liên quan không thể hiển thị hoặc xuất PDF.")}</p>}
          {job.job_files?.length ? <ul className={ui('job-files')} aria-label={t("Trạng thái từng tệp")}>
            {job.job_files.map(file => <li key={file.id} className={ui('job-file')}>
              <div className={ui('job-file-details')}><strong>{file.original_filename || t("Tài liệu #{0}", file.document_id)}</strong>
                <p className={ui('job-file-attempts')}>{t("Lần thử") + " "}{file.attempt_count}/3{file.timeout_seconds != null && t(" · Giới hạn {0} giây", file.timeout_seconds)}</p>
                {file.error_message && <p className={ui('job-file-error')}>{errorText(file.error_message)}</p>}</div>
              <Badge status={file.status} />
            </li>)}
          </ul> : <p className={ui('muted')}>{t("Chưa có thông tin tệp.")}</p>}
          {job.mode === 'table' && <ExportTableButton job={job} jobId={jobId} />}
          <AnalysisResults data={job.result_data} jobId={jobId} mode={job.mode} jobFiles={job.job_files} />
        </>}
      </section>
    </main>
  </>;
}

export async function getServerSideProps({ req, res, params }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  if (!user) return { redirect: { destination: '/', permanent: false } };
  if (!/^[1-9]\d*$/.test(params.jobId)) return { notFound: true };
  return { props: { jobId: params.jobId, initialLocale: readLocale(req.headers.cookie) } };
}
