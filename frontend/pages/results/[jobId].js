import Head from 'next/head';
import { useEffect, useState } from 'react';
import { getSession } from '../../lib/session';
import AnalysisResults from '../../components/AnalysisResults';

const labels = {
  pending: 'Pending', processing: 'Processing', completed: 'Completed',
  failed: 'Failed', timed_out: 'Timed out',
};
const terminal = new Set(['completed', 'failed', 'timed_out']);

function Badge({ status }) {
  return <span className={`job-badge job-${status}`}>{labels[status] || 'Unknown'}</span>;
}

export default function Results({ jobId }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');

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
          setError('Không tìm thấy tác vụ hoặc bạn không có quyền truy cập.');
          return;
        }
        if (!response.ok) throw new Error('Cannot fetch job');
        const next = await response.json();
        if (stopped) return;
        setJob(next);
        setError('');
        if (terminal.has(next.status)) return;
      } catch (err) {
        if (stopped || err.name === 'AbortError') return;
        setError('Không thể cập nhật tiến độ. Hệ thống sẽ tự thử lại.');
      }
      if (!stopped) timer = setTimeout(poll, 3000);
    }

    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
      controller.abort();
    };
  }, [jobId]);

  const total = job?.file_count || 0;
  const completed = Math.min(total, Math.max(0, job?.completed_count || 0));

  return <>
    <Head><title>DocuMind · Tiến độ xử lý</title></Head>
    <main className="workspace results-page">
      <header><a href="/workspace" className="brand">DocuMind<span className="brand-dot">.</span></a>
        <a className="btn" href="/workspace">Về không gian tài liệu</a></header>
      <section className="results-content">
        <p className="eyebrow">TÁC VỤ #{jobId}</p>
        <h1>Tiến độ xử lý</h1>
        {!job && !error && <p role="status">Đang tải tiến độ…</p>}
        {error && <p className="error-box" role="alert">{error}</p>}
        {job && <>
          <section className="job-progress-card" aria-label="Tiến độ tác vụ">
            <div className="job-progress-heading"><h2>Trạng thái xử lý</h2>
              <span aria-label="Trạng thái job" role="status"><Badge status={job.status} /></span></div>
            <p className="job-count" aria-live="polite">{completed}/{total} tệp đã xử lý thành công</p>
            <progress aria-label="Tiến độ xử lý" max={total || 1} value={completed}
              aria-valuetext={`${completed}/${total} tệp đã xử lý thành công`} />
            <p className="job-progress-note">{job.status === 'completed'
              ? 'Tất cả tài liệu đã được xử lý xong.'
              : job.status === 'failed' ? 'Tác vụ kết thúc với lỗi. Xem chi tiết từng tệp bên dưới.'
              : job.status === 'timed_out' ? 'Tác vụ đã vượt quá thời gian xử lý cho phép.'
              : 'Tiến độ tự cập nhật mỗi 3 giây. Bạn có thể quay lại trang này sau.'}</p>
          </section>
          <h2 className="job-files-heading">Trạng thái từng tệp</h2>
          {job.job_files?.length ? <ul className="job-files" aria-label="Trạng thái từng tệp">
            {job.job_files.map(file => <li key={file.id} className="job-file">
              <div className="job-file-details"><strong>{file.original_filename || `Tài liệu #${file.document_id}`}</strong>
                <p className="job-file-attempts">Lần thử {file.attempt_count}/3{file.timeout_seconds != null && ` · Giới hạn ${file.timeout_seconds} giây`}</p>
                {file.error_message && <p className="job-file-error">{file.error_message}</p>}</div>
              <Badge status={file.status} />
            </li>)}
          </ul> : <p className="muted">Chưa có thông tin tệp.</p>}
          <AnalysisResults data={job.result_data} jobId={jobId} />
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
  return { props: { jobId: params.jobId } };
}
