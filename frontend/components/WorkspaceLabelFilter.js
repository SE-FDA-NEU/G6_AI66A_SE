import { useEffect, useState } from 'react';

export default function WorkspaceLabelFilter({ label, folderName, hasFolder, onApply, onClear, onClearAll }) {
  const [draft, setDraft] = useState(label);
  useEffect(() => { setDraft(label); }, [label]);

  return (
    <section className="workspace-label-filter" aria-label="Lọc danh sách tài liệu">
      <form onSubmit={event => { event.preventDefault(); if (draft.trim()) onApply(draft.trim()); }}>
        <label htmlFor="document-ai-label-filter">Nhãn AI hiển thị</label>
        <p id="ai-label-filter-help" className="search-help">Khớp chính xác nhãn AI, phân biệt hoa/thường và dấu; không dùng nhãn người dùng.
          {' '}Khi chọn cả thư mục và nhãn, tài liệu phải khớp đồng thời cả hai. Bộ lọc này áp dụng cho danh sách; tìm kiếm có bộ lọc riêng.</p>
        <div className="label-filter-controls">
          <input id="document-ai-label-filter" value={draft} maxLength={100} placeholder="Ví dụ: Macroeconomics"
            aria-describedby="ai-label-filter-help" onChange={event => setDraft(event.target.value)} />
          <button className="btn" disabled={!draft.trim()}>Áp dụng nhãn AI</button>
          <button type="button" className="btn" disabled={!label && !draft}
            onClick={() => { setDraft(''); onClear(); }}>Xóa lọc nhãn AI</button>
          <button type="button" className="btn" disabled={!label && !draft && !hasFolder}
            onClick={() => { setDraft(''); onClearAll(); }}>Xóa lọc danh sách</button>
        </div>
      </form>
      <p role="status" className="search-help">{label ? `Nhãn AI: “${label}”` : 'Tất cả nhãn AI'} · {hasFolder ? `Thư mục: “${folderName || 'thư mục đã chọn'}”` : 'Tất cả thư mục'}</p>
    </section>
  );
}
