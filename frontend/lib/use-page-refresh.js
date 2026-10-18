import { useEffect, useRef } from 'react';

// Revalidate on return from another tab or browser history, without polling or
// opening every document just to read its metadata.
export default function usePageRefresh(callback) {
  const latest = useRef(callback);
  latest.current = callback;
  useEffect(() => {
    let timer;
    function refresh() {
      if (document.visibilityState !== 'visible') return;
      clearTimeout(timer);
      timer = setTimeout(() => latest.current(), 50);
    }
    function restored(event) { if (event.persisted) refresh(); }
    window.addEventListener('pageshow', restored);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('pageshow', restored);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, []);
}
