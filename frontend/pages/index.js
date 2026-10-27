import ProductOverview from '../components/ProductOverview';
import { ArrowRight, FileText, ShieldCheck, CornerDownRight } from 'lucide-react';
import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { readLocale } from '../lib/i18n';
import Head from 'next/head';
import { useEffect, useState } from 'react';
import { getSession } from '../lib/session';

export default function Landing() {
  const { t, locale, errorText } = useI18n();
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
        throw new Error(typeof result.detail === 'string' ? result.detail : t("Không thể đăng nhập. Vui lòng thử lại."));
      }
      window.location.assign('/workspace');
    } catch (err) {
      setError(err instanceof TypeError ? t("Không thể kết nối máy chủ. Vui lòng thử lại.") : err.message);
      setBusy(false);
    }
  }
  return <>
    <Head><title>{t("DocuMind · Đăng nhập")}</title><meta name="description" content={t("Tóm tắt, phân loại và tìm kiếm tài liệu trong không gian riêng của bạn.")} /></Head>
    <main className="auth-page mx-auto min-h-screen max-w-7xl border-x border-line">
      <header className="flex h-14 items-center justify-between border-b border-line px-5 sm:px-6">
        <a href="/" className={ui('brand')}><span className="size-2 bg-emerald-500 motion-safe:animate-pulse rounded-full" aria-hidden="true"/>DOCUMIND<span className="text-zinc-600">/</span></a>
        <nav aria-label={t('Điều hướng giới thiệu')} className="flex items-center gap-5 text-xs text-zinc-400">
          <a href="#modules" className="hidden hover:text-white sm:block">{t('Tính năng')}</a>
          <a href="#preview" className="hidden hover:text-white sm:block">{t('Xem minh họa')}</a>
          <a href="#login" className={ui('btn')}>{t('Bắt đầu')} ↗</a>
        </nav>
      </header>
      <div className="grid border-b border-line lg:grid-cols-[1.35fr_1fr]">
        <section className="auth-story px-6 py-14 sm:px-10 sm:py-20" aria-label={t('Giới thiệu DocuMind')}>
          <p className="mb-8 font-mono text-[10px] tracking-[.2em] text-zinc-500">01 // DOCUMENT_INTELLIGENCE</p>
          <h1 className="max-w-2xl text-4xl leading-[1.12] font-semibold tracking-tight sm:text-6xl">{t('Biến tài liệu thành')}<br/><span className="text-orange-500">{t('điều bạn cần biết.')}</span></h1>
          <p className="mt-6 max-w-lg text-base leading-8 text-zinc-400">{t('Tóm tắt nội dung, gợi ý nhãn và tìm lại thông tin. Một không gian gọn gàng cho mọi tài liệu của bạn.')}</p>
          <div className="mt-9 flex flex-wrap gap-3"><a href="#login" className={ui('btn primary')}>{t('Mở không gian tài liệu')}<ArrowRight size={15}/></a><a href="#preview" className={ui('btn')}>{t('Xem kết quả mẫu')}</a></div>
          <div className="mt-12 flex flex-wrap items-center gap-5 font-mono text-[10px] text-zinc-500"><span className="inline-flex items-center gap-2"><FileText size={13}/>PDF / DOCX / PPTX</span><span className="inline-flex items-center gap-2"><ShieldCheck size={13}/>{t('Có dẫn nguồn')}</span></div>
        </section>
        <section id="login" className="auth-form-wrap scroll-mt-4 border-t border-line bg-surface px-6 py-10 sm:px-10 lg:flex lg:items-center lg:border-t-0 lg:border-l">
          <div className="auth-form w-full">
            <p className="mb-6 font-mono text-[10px] tracking-[.18em] text-zinc-500">ACCESS // YOUR_WORKSPACE</p>
            <h2 className="text-2xl font-semibold">{t('Tiếp tục công việc của bạn')}</h2>
            <p className="mt-3 mb-7 text-sm leading-7 text-zinc-400">{t('Đăng nhập để mở không gian tài liệu cá nhân.')}</p>
            <form onSubmit={submit} method="post" aria-busy={busy} className="space-y-5">
              <div role="alert" aria-live="polite" id="login-error">{error && <p className={ui('error-box')}>{errorText(error)}</p>}</div>
              <div><label htmlFor="email">{t('Email')}</label><input id="email" name="email" type="email" autoComplete="username" placeholder={t('ban@example.com')} required maxLength={255} disabled={busy} aria-describedby={error ? 'login-error' : undefined}/></div>
              <div><label htmlFor="password">{t('Mật khẩu')}</label><input id="password" name="password" type="password" autoComplete="current-password" placeholder={t('Nhập mật khẩu của bạn')} required disabled={busy} aria-describedby={error ? 'login-error' : undefined}/></div>
              <button className={ui('btn primary w-full justify-between')} type="submit" disabled={!ready || busy}>{busy ? t('Đang đăng nhập…') : t('Đăng nhập')}<ArrowRight size={15} aria-hidden="true"/></button>
            </form>
            <p className="mt-7 flex gap-2 border-t border-line pt-5 text-xs leading-6 text-zinc-500"><ShieldCheck size={14} className="mt-1"/>{t('Tài liệu cá nhân chỉ được truy cập sau khi đăng nhập.')}</p>
          </div>
        </section>
      </div>
      <section aria-label={t('Quy trình minh họa')} className="border-b border-line p-5 sm:p-8">
        <div className="border border-line bg-surface">
          <div className="flex items-center gap-1.5 border-b border-line px-4 py-3"><span className="size-1.5 rounded-full bg-zinc-600"/><span className="size-1.5 rounded-full bg-zinc-700"/><span className="size-1.5 rounded-full bg-zinc-800"/><span className="ml-3 font-mono text-[9px] text-zinc-500">documind / pipeline.example</span><span className="ml-auto font-mono text-[9px] text-orange-400">{t('MINH HỌA')}</span></div>
          <div className="grid gap-px bg-line md:grid-cols-3">{[['01', 'Tải tài liệu', 'PDF, DOCX hoặc PPTX'], ['02', 'Chọn kiểu phân tích', 'Tóm tắt · Bảng điều khoản · Khái niệm'], ['03', 'Đọc & kiểm tra nguồn', 'Mở kết quả và đối chiếu trang gốc']].map(([index, title, detail]) => <div key={index} className="bg-surface px-5 py-7"><p className="mb-4 font-mono text-[10px] text-zinc-600">STEP_{index}</p><h3 className="flex items-center gap-2 text-sm"><CornerDownRight size={14} className="text-orange-500"/>{t(title)}</h3><p className="mt-2 pl-6 text-xs leading-6 text-zinc-500">{t(detail)}</p></div>)}</div>
        </div>
      </section>
      <ProductOverview/>
    </main>
  </>;
}

export async function getServerSideProps({ req, res }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  return user ? { redirect: { destination: '/workspace', permanent: false } } : { props: { initialLocale: readLocale(req.headers.cookie) } };
}
