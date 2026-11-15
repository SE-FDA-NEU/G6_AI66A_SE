import { useEffect, useRef, useState } from 'react';
import { useI18n } from '../lib/i18n';

export default function PptxPreview({ documentId, page, onFallback }) {
  const { t } = useI18n();
  const frame = useRef(null);
  const bytes = useRef(null);
  const pageRef = useRef(page);
  pageRef.current = page;
  const [status, setStatus] = useState('loading');
  const [ratio, setRatio] = useState(9 / 16);
  const [srcDoc, setSrcDoc] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let ready = false;
    let sent = false;
    setStatus('loading');
    const send = () => {
      if (!ready || !bytes.current || sent) return;
      sent = true;
      const buffer = bytes.current.slice(0);
      frame.current?.contentWindow?.postMessage({ type: 'pptx:init', buffer, page: pageRef.current }, '*', [buffer]);
    };
    const receive = event => {
      if (event.source !== frame.current?.contentWindow || !event.data) return;
      if (event.data.type === 'pptx:ready') { ready = true; send(); }
      if (event.data.type === 'pptx:loaded' && Number.isFinite(event.data.ratio) && event.data.ratio > 0 && event.data.ratio < 10)
        setRatio(event.data.ratio);
      if (event.data.type === 'pptx:rendered') setStatus('ready');
      if (event.data.type === 'pptx:error') setStatus('error');
    };
    window.addEventListener('message', receive);
    // Explicit script URL works inside the opaque-origin sandbox. Document
    // content cannot fetch external URLs, execute inline JS, or reach cookies.
    const script = new URL('/pptx-renderer.js', window.location.origin).href;
    setSrcDoc(`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src ${window.location.origin}; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'"><style>html,body{margin:0;padding:0;overflow:hidden;background:white}#slide{width:1280px;transform-origin:top left}*{box-sizing:border-box}body{font-family:Arial,sans-serif}</style></head><body><div id="slide"></div><script src="${script}"></script></body></html>`);
    const timer = setTimeout(() => setStatus(current => current === 'loading' ? 'error' : current), 30000);
    bytes.current = null;
    fetch(`/api/documents/${documentId}/file`, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(); return response.arrayBuffer(); })
      .then(buffer => { if (!controller.signal.aborted) { bytes.current = buffer; send(); } })
      .catch(error => { if (error.name !== 'AbortError') setStatus('error'); });
    return () => {
      controller.abort(); clearTimeout(timer); bytes.current = null;
      window.removeEventListener('message', receive);
    };
  }, [documentId]);
  useEffect(() => {
    frame.current?.contentWindow?.postMessage({ type: 'pptx:page', page }, '*');
  }, [page]);
  return <section aria-label={t('PowerPoint preview')} data-testid="pptx-preview" data-status={status}>
    {status === 'loading' && <p role="status">{t('Loading slide preview…')}</p>}
    {status === 'error' && <div role="alert">
      <p>{t('This slide could not be previewed. You can open the text reader or download the original PowerPoint.')}</p>
      <button type="button" onClick={onFallback}>{t('Open text reader')}</button>
      <a href={`/api/documents/${documentId}/file`}>{t('Download original PowerPoint')}</a>
    </div>}
    <iframe ref={frame} title={t('PowerPoint slide {0}', page)} sandbox="allow-scripts"
      referrerPolicy="no-referrer" srcDoc={srcDoc || undefined}
      style={{ display: status === 'error' ? 'none' : 'block', width: '100%', aspectRatio: `1 / ${ratio}`, border: 0, background: 'white' }} />
  </section>;
}
