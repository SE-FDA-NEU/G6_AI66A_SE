import Head from 'next/head';
import { useEffect, useState } from 'react';
import { getSession } from '../lib/session';

export default function Landing() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch('/auth/login', {
        method: 'POST', credentials: 'same-origin',
        body: new URLSearchParams({ username: data.get('email').trim(), password: data.get('password') }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(typeof result.detail === 'string' ? result.detail : 'Không thể đăng nhập. Vui lòng thử lại.');
      }
      window.location.assign('/workspace');
    } catch (err) {
      setError(err instanceof TypeError ? 'Không thể kết nối máy chủ. Vui lòng thử lại.' : err.message);
      setBusy(false);
    }
  }
  return <>
    <Head><title>DocuMind · Đăng nhập</title><meta name="description" content="Tóm tắt, phân loại và tìm kiếm tài liệu trong không gian riêng của bạn." /></Head>
    <main className="auth-page">
      <section className="auth-story" aria-label="Giới thiệu DocuMind">
        <a href="/" className="brand"><span className="brand-mark">D</span>DocuMind<span className="brand-dot">.</span></a>
        <div className="story-content"><p className="eyebrow">ĐỌC ÍT HƠN. HIỂU NHIỀU HƠN.</p>
          <h1>Biến tài liệu thành<br /><em>điều bạn cần biết.</em></h1>
          <p className="story-description">Tóm tắt nội dung, gợi ý nhãn và tìm lại thông tin. Một không gian gọn gàng cho mọi tài liệu của bạn.</p>
          <div className="preview-card"><div className="preview-heading"><strong>Từ tài liệu đến thông tin</strong><span className="badge">Có dẫn nguồn</span></div>
            <div className="document-preview"><span className="file-type">PDF</span><div><strong>Hợp đồng dịch vụ.pdf</strong><p>Giá trị · Thanh toán · Điều khoản phạt</p></div></div>
            <p className="preview-note">Đối chiếu thông tin ngay tại đoạn văn bản gốc.</p>
          </div>
        </div><p className="story-footer">TÀI LIỆU CỦA BẠN · KHÔNG GIAN CỦA BẠN</p>
      </section>
      <section className="auth-form-wrap"><div className="auth-form">
        <p className="eyebrow">CHÀO MỪNG ĐẾN DOCUMIND</p><h2>Tiếp tục công việc của bạn</h2>
        <p className="muted">Đăng nhập để mở không gian tài liệu cá nhân.</p>
        <form onSubmit={submit} method="post" aria-busy={busy}>
          <div role="alert" aria-live="polite" id="login-error">{error && <p className="error-box">{error}</p>}</div>
          <div className="field"><label htmlFor="email">Email</label><input id="email" name="email" type="email" autoComplete="username" placeholder="ban@example.com" required maxLength={255} disabled={busy} aria-describedby={error ? 'login-error' : undefined} /></div>
          <div className="field"><label htmlFor="password">Mật khẩu</label><input id="password" name="password" type="password" autoComplete="current-password" placeholder="Nhập mật khẩu của bạn" required disabled={busy} aria-describedby={error ? 'login-error' : undefined} /></div>
          <button className="btn primary" type="submit" disabled={!ready || busy}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}<span aria-hidden="true">→</span></button>
        </form>
        <p className="privacy-note">Tài liệu cá nhân chỉ được truy cập sau khi đăng nhập.</p>
      </div></section>
    </main>
  </>;
}

export async function getServerSideProps({ req, res }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  return user ? { redirect: { destination: '/workspace', permanent: false } } : { props: {} };
}
