import { useEffect, useState } from 'react';

export default function useFolders() {
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true); setError('');
      try {
        const collected = [];
        for (let skip = 0; ; skip += 100) {
          const response = await fetch(`/api/folders?skip=${skip}&limit=100`, { signal: controller.signal, cache: 'no-store' });
          if (response.status === 401) { window.location.assign('/'); return; }
          if (!response.ok) throw new Error();
          const batch = await response.json();
          if (!Array.isArray(batch) || batch.some(folder => !Number.isSafeInteger(folder.id) || typeof folder.name !== 'string')) throw new Error();
          if (batch.some(folder => collected.some(existing => existing.id === folder.id))) throw new Error();
          collected.push(...batch);
          if (batch.length < 100) break;
        }
        if (!controller.signal.aborted) setFolders(collected);
      } catch {
        if (!controller.signal.aborted) setError('Không thể tải thư mục. Vui lòng thử lại.');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [attempt]);

  return { folders, loading, error, reload: () => setAttempt(value => value + 1),
    add: folder => setFolders(current => [folder, ...current.filter(item => item.id !== folder.id)]) };
}
