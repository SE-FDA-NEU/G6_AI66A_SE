export default function WorkspacePagination({ label, page, hasNext, busy, onPage }) {
  return (
    <nav className="workspace-pagination" aria-label={label}>
      <button className="btn" disabled={busy || page === 0} onClick={() => onPage(page - 1)}>Trang trước</button>
      <span aria-live="polite">Trang {page + 1}</span>
      <button className="btn" disabled={busy || !hasNext} onClick={() => onPage(page + 1)}>Trang sau</button>
    </nav>
  );
}
