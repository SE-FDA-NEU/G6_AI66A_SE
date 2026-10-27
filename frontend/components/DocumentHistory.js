import { useEffect, useMemo, useState } from 'react';
import { MessageSquare, Search, SlidersHorizontal, X, Folder, ChevronDown, ChevronRight } from 'lucide-react';
import { useI18n } from '../lib/i18n';
import { ui } from '../lib/ui';
import DocumentMetadata from './DocumentMetadata';
import DocumentExpiry from './DocumentExpiry';
import DocumentLabelEditor from './DocumentLabelEditor';
import DocumentFolderMove from './DocumentFolderMove';
import WorkspacePagination from './WorkspacePagination';

const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().trim();
const PAGE_SIZE = 10;

export default function DocumentHistory({ folderId, folders, foldersUnavailable, refreshKey, onMoved, onLabelSaved, onCreateFolder, onSelectFolder, foldersLoading = false, folderError = false, onRetryFolders }) {
  const { t } = useI18n();
  const [documents, setDocuments] = useState([]);
  const [query, setQuery] = useState('');
  const [pages, setPages] = useState({});
  const [openFolders, setOpenFolders] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [expanded, setExpanded] = useState({});
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true); setError(false);
      try {
        const collected = [];
        const ids = new Set();
        // The existing label API is exact/AI-only. Read metadata pages so
        // history can search partial user and AI labels across the whole list.
        for (let skip = 0; ; skip += 100) {
          const params = new URLSearchParams({ skip: String(skip), limit: '100' });
          const response = await fetch(`/api/documents?${params}`, { signal: controller.signal, cache: 'no-store' });
          if (response.status === 401) { window.location.assign('/'); return; }
          if (!response.ok) throw new Error();
          const batch = await response.json();
          if (!Array.isArray(batch)) throw new Error();
          for (const doc of batch) {
            if (!Number.isSafeInteger(doc.id) || typeof doc.original_filename !== 'string' || ids.has(doc.id)) throw new Error();
            ids.add(doc.id); collected.push(doc);
          }
          if (batch.length < 100) break;
        }
        if (!controller.signal.aborted) setDocuments(collected);
      } catch { if (!controller.signal.aborted) setError(true); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    load();
    return () => controller.abort();
  }, [refreshKey, attempt]);
  const filtered = useMemo(() => {
    const term = normalize(query);
    return term ? documents.filter(doc => [doc.user_label, doc.ai_label].some(label => normalize(label).includes(term))) : documents;
  }, [documents, query]);
  useEffect(() => {
    if (folderId && folderId !== 'unassigned') setOpenFolders(current => ({ ...current, [folderId]: true }));
  }, [folderId]);
  const knownIds = new Set(folders.map(folder => folder.id));
  const outside = filtered.filter(doc => doc.folder_id == null);
  const unknown = filtered.filter(doc => doc.folder_id != null && !knownIds.has(doc.folder_id));
  function documentMoved(document) {
    const key = document.folder_id == null ? 'outside' : String(document.folder_id);
    if (document.folder_id != null) setOpenFolders(current => ({ ...current, [document.folder_id]: true }));
    const destination = filtered.filter(doc => doc.id === document.id || (doc.folder_id ?? null) === document.folder_id);
    setPages(current => ({ ...current, [key]: Math.max(0, Math.floor(destination.findIndex(doc => doc.id === document.id) / PAGE_SIZE)) }));
    onMoved(document);
  }

  function renderDocuments(items, key, label) {
    const lastPage = Math.max(0, Math.ceil(items.length / PAGE_SIZE) - 1);
    const currentPage = Math.min(pages[key] || 0, lastPage);
    if (!items.length) return null;
    return <>
        <ul className="space-y-1" aria-label={label}>
          {items.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).map(doc => <li key={doc.id} data-testid="workspace-document-row" data-document-id={doc.id} className="workspace-document-row relative min-w-0 border-b border-line pb-1">
            <a href={`/documents/${doc.id}?page=1`} className="document-row-title flex min-h-16 min-w-0 gap-3 py-3 pr-12 pl-2" aria-label={doc.original_filename}>
              <MessageSquare size={15} className="mt-1 text-zinc-500"/>
              <div className="min-w-0 flex-1"><strong className="block truncate text-sm font-medium text-zinc-200">{doc.user_label?.trim() || doc.ai_label?.trim() || t('Chưa có nhãn')}</strong><span className="mt-1 block truncate text-[11px] text-zinc-500" title={doc.original_filename}>{doc.original_filename}</span></div>
            </a>
            <details className="history-options px-2" open={Boolean(expanded[doc.id])} onToggle={event => {
              const open = event.currentTarget.open;
              setExpanded(current => Boolean(current[doc.id]) === open ? current : { ...current, [doc.id]: open });
            }}>
              <summary className="absolute top-2 right-0 grid size-11 place-items-center text-zinc-500" aria-label={t('Tùy chọn {0}', doc.original_filename)} title={t('Nhãn và thư mục')}><SlidersHorizontal size={14}/><span className="sr-only">{t('Nhãn và thư mục')}</span></summary>
              <div className="space-y-3 pb-3"><DocumentExpiry expiresAt={doc.expires_at}/><DocumentMetadata document={doc} folderName={folders.find(folder => folder.id === doc.folder_id)?.name}/>
                <DocumentLabelEditor documentId={doc.id} document={doc} onSaved={onLabelSaved}/>
                <DocumentFolderMove document={doc} folders={folders} foldersUnavailable={foldersUnavailable} onMoved={documentMoved} onCreateFolder={onCreateFolder}/>
              </div>
            </details>
          </li>)}
        </ul>
      {lastPage > 0 && <WorkspacePagination label={label} page={currentPage} hasNext={currentPage < lastPage} busy={loading} onPage={page => setPages(current => ({ ...current, [key]: page }))}/>}
    </>;
  }
  return <section className="workspace-documents min-w-0 space-y-4" aria-label={t('Lịch sử tài liệu')} aria-busy={loading}>
    <div className="flex items-center justify-between"><h2 className="text-xs font-medium text-zinc-400">{t('Lịch sử tài liệu')}</h2><span className="font-mono text-[10px] text-zinc-500">{!loading && !error ? filtered.length : '…'}</span></div>
    <div className="relative"><Search size={14} className="pointer-events-none absolute top-3.5 left-3 text-zinc-500"/>
      <label htmlFor="history-label-search" className="sr-only">{t('Tìm lịch sử theo nhãn')}</label>
      <input id="history-label-search" type="search" maxLength={100} placeholder={t('Tìm theo nhãn…')} value={query} className="pr-10 pl-9 text-sm" onChange={event => { setQuery(event.target.value); setPages({}); }}/>
      {query && <button type="button" className="absolute top-1 right-1 grid size-9 place-items-center text-zinc-400" aria-label={t('Xóa tìm kiếm nhãn')} onClick={() => { setQuery(''); setPages({}); }}><X size={14}/></button>}
    </div>
    {loading && <p role="status" className="py-3 text-xs text-zinc-500">{t('Đang tải lịch sử…')}</p>}
    {error && <div role="alert" className="space-y-3 text-xs text-orange-300"><p>{t('Không thể tải danh sách tài liệu. Vui lòng thử lại.')}</p><button className={ui('btn')} onClick={() => setAttempt(value => value + 1)}>{t('Thử lại danh sách')}</button></div>}
    {foldersLoading && <p role="status" className="text-xs text-zinc-500">{t('Đang tải thư mục…')}</p>}
    {folderError && <div role="alert" className="space-y-2 text-xs text-orange-300"><p>{t('Không thể tải thư mục. Vui lòng thử lại.')}</p><button className={ui('btn')} onClick={onRetryFolders}>{t('Thử lại thư mục')}</button></div>}
    <div className="space-y-1" aria-label={t('Các thư mục')}>
      {folders.map(folder => {
        const items = filtered.filter(doc => doc.folder_id === folder.id);
        if (query.trim() && !items.length && !loading) return null;
        const open = Boolean(query.trim()) || Boolean(openFolders[folder.id]);
        const selected = String(folder.id) === folderId;
        return <section key={folder.id} data-folder-id={folder.id} aria-label={t('Thư mục {0}', folder.name)}>
          <div className={`flex items-center ${selected ? 'border-l-2 border-orange-500 bg-hover' : ''}`}>
            <button type="button" className="flex min-h-11 min-w-0 flex-1 items-center gap-2 px-2 text-left text-xs text-zinc-300" aria-current={selected ? 'page' : undefined} aria-label={t('Mở thư mục {0}', folder.name)} onClick={() => { setOpenFolders(current => ({ ...current, [folder.id]: true })); onSelectFolder(String(folder.id)); }}><Folder size={15} className="text-orange-400"/><span className="min-w-0 flex-1 truncate" title={folder.name}>{folder.name}</span><span className="font-mono text-[10px] text-zinc-500">{!loading && !error ? items.length : '…'}</span></button>
            <button type="button" className="grid size-11 shrink-0 place-items-center text-zinc-500" aria-label={t('Danh sách trong {0}', folder.name)} aria-expanded={open} aria-controls={`history-folder-${folder.id}`} onClick={() => setOpenFolders(current => ({ ...current, [folder.id]: !open }))}>{open ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}</button>
          </div>
          <div id={`history-folder-${folder.id}`} hidden={!open} className="ml-4 border-l border-line pl-2">
            {open && !loading && !error && (items.length ? renderDocuments(items, String(folder.id), t('Lịch sử trong {0}', folder.name)) : <p className="py-3 text-xs leading-6 text-zinc-500">{t('Thư mục này chưa có tài liệu.')}</p>)}
          </div>
        </section>;
      })}
      {!foldersLoading && !folderError && !folders.length && <p className="py-2 text-xs text-zinc-500">{t('Chưa có thư mục. Tạo thư mục để sắp xếp tài liệu.')}</p>}
    </div>
    {!loading && !error && <>
      {query.trim() && !filtered.length && <p className="text-xs leading-6 text-zinc-500">{t('Không tìm thấy nhãn phù hợp. Thử một từ khác.')}</p>}
      {!!unknown.length && <section className="space-y-2" aria-label={t('Thư mục chưa tải')}><h3 className="text-xs text-zinc-500">{t('Thư mục chưa tải')}</h3>{renderDocuments(unknown, 'unknown', t('Lịch sử trong thư mục chưa tải'))}</section>}
      <section aria-label="Recents">
        <button type="button" className="mb-2 flex min-h-11 w-full items-center justify-between gap-2 border-t border-line px-2 pt-2 text-left text-xs text-zinc-400" aria-current={!folderId || folderId === 'unassigned' ? 'page' : undefined} onClick={() => onSelectFolder('')}>Recents<MessageSquare size={14}/></button>
        {renderDocuments(outside, 'outside', t('Phân trang tài liệu'))}
        {!query.trim() && !outside.length && <p className="py-2 text-xs leading-6 text-zinc-500">{t('Chưa có tài liệu ngoài thư mục.')}</p>}
      </section>
    </>}
  </section>;
}
