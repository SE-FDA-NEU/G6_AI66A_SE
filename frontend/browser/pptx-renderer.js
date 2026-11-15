// Runs only inside an opaque-origin sandbox, with no network/API access.
import { init } from 'pptx-preview';
let previewer;
let currentPage = 1;
let loaded = false;
let loading = false;
const host = document.getElementById('slide');
function notify(type, extra = {}) { parent.postMessage({ type, ...extra }, '*'); }
function render() {
  if (!loaded) return;
  if (!Number.isInteger(currentPage) || currentPage < 1 || currentPage > previewer.slideCount) return;
  previewer.renderSingleSlide(currentPage - 1);
  notify('pptx:rendered', { page: currentPage, count: previewer.slideCount });
}
window.addEventListener('message', async event => {
  if (event.source !== parent || !event.data || typeof event.data !== 'object') return;
  const { type, page, buffer } = event.data;
  if (type === 'pptx:page') {
    currentPage = page;
    try { render(); } catch { notify('pptx:error'); }
    return;
  }
  if (type !== 'pptx:init' || loading || !(buffer instanceof ArrayBuffer)) return;
  loading = true;
  currentPage = page;
  try {
    previewer = init(host, { width: 1280, height: 720, mode: 'slide' });
    await previewer.load(buffer);
    // Use the presentation's own aspect ratio instead of forcing widescreen.
    const { width, height } = previewer.pptx;
    if (!(width > 0 && height > 0 && Number.isFinite(width / height))) throw new Error();
    const canvasHeight = 1280 * height / width;
    previewer.options.height = canvasHeight;
    previewer.wrapper.style.height = `${canvasHeight}px`;
    previewer.htmlRender.options.viewPort.height = canvasHeight;
    loaded = true;
    notify('pptx:loaded', { ratio: height / width, count: previewer.slideCount });
    render();
    const fit = () => {
      host.style.transform = `scale(${window.innerWidth / 1280})`;
    };
    window.addEventListener('resize', fit);
    fit();
  } catch {
    host.replaceChildren();
    notify('pptx:error');
  }
});
notify('pptx:ready');
