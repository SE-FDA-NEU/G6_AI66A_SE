import Head from 'next/head';
import { useEffect, useRef, useState } from 'react';
import { getSession } from '../lib/session';
import { MB, validateSelection } from '../lib/upload-validation';

export default function Upload() {
  const [entries, setEntries] = useState([]);
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  const nextId = useRef(0);
  const accepted = entries.filter(entry => entry.errors.length === 0);
  const rejected = entries.length - accepted.length;
  const total = accepted.reduce((sum, entry) => sum + entry.file.size, 0);

  function addFiles(files) {
    const additions = Array.from(files, file => ({ id: nextId.current++, file }));
    setEntries(previous => {
      // Keep accepted files first so new/rejected files cannot displace them.
      const valid = previous.filter(entry => entry.errors.length === 0);
      const invalid = previous.filter(entry => entry.errors.length > 0);
      return validateSelection([...valid, ...invalid, ...additions]);
    });
  }

  function removeFile(id) {
    setEntries(previous => {
      const remaining = previous.filter(entry => entry.id !== id);
      return validateSelection([
        ...remaining.filter(entry => entry.errors.length === 0),
        ...remaining.filter(entry => entry.errors.length > 0),
      ]);
    });
  }

  return <>
    <Head><title>DocuMind · Tải tài liệu</title></Head>
    <main className="workspace upload-page">
      <header>
        <a href="/workspace" className="brand">DocuMind<span className="brand-dot">.</span></a>
        <a href="/workspace" className="btn">Về không gian tài liệu</a>
      </header>
      <section className="upload-content">
        <p className="eyebrow">THÊM TÀI LIỆU</p>
        <h1>Tải tài liệu</h1>
        <p className="muted">Chọn tài liệu để kiểm tra trước khi tải lên.</p>
        <div className="upload-picker" onDragOver={event => event.preventDefault()}
          onDrop={event => { event.preventDefault(); addFiles(event.dataTransfer.files); }}>
          <h2>Chọn hoặc kéo thả tệp vào đây</h2>
          <p id="upload-rules">PDF, DOCX hoặc PPTX · Tối đa 5 tệp · Mỗi tệp ≤ 5 MB · Tổng ≤ 50 MB</p>
          <label htmlFor="upload-files">Chọn tệp tài liệu</label>
          <input id="upload-files" type="file" multiple accept=".pdf,.docx,.pptx" disabled={!ready}
            aria-describedby="upload-rules" onChange={event => {
              addFiles(event.target.files);
              event.target.value = '';
            }} />
        </div>
        <div role="status" className="upload-summary">
          {accepted.length}/5 tệp hợp lệ · {(total / MB).toFixed(2)} MB
          {rejected > 0 && <span> · {rejected} tệp cần kiểm tra</span>}
        </div>
        {entries.length > 0 && <ul className="upload-files" aria-label="Tệp đã chọn">
          {entries.map(entry => <li key={entry.id} className="upload-file">
            <div className="upload-file-info">
              <strong>{entry.file.name}</strong>
              <span className="upload-size">{(entry.file.size / MB).toFixed(2)} MB</span>
              {entry.errors.length > 0
                ? <div role="alert" className="upload-errors">{entry.errors.map(error =>
                  <span className="upload-error-badge" key={error}>{error}</span>)}</div>
                : <span className="badge">Hợp lệ</span>}
            </div>
            <button type="button" className="btn" aria-label={`Xóa ${entry.file.name}`}
              onClick={() => removeFile(entry.id)}>Xóa</button>
          </li>)}
        </ul>}
        {accepted.length > 0 && rejected === 0 && <p className="upload-ready">Các tệp đã chọn hợp lệ và sẵn sàng tải lên.</p>}
      </section>
    </main>
  </>;
}

export async function getServerSideProps({ req, res }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  return user ? { props: {} } : { redirect: { destination: '/', permanent: false } };
}
