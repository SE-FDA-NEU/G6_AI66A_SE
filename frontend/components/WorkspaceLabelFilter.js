import { useI18n } from '../lib/i18n';
import { useEffect, useState } from 'react';

export default function WorkspaceLabelFilter({ label, folderName, hasFolder, onApply, onClear, onClearAll }) {
  const { t, locale, errorText } = useI18n();
  const [draft, setDraft] = useState(label);
  useEffect(() => { setDraft(label); }, [label]);

  return (
    <section className="workspace-label-filter" aria-label={t("Lọc danh sách tài liệu")}>
      <form onSubmit={event => { event.preventDefault(); if (draft.trim()) onApply(draft.trim()); }}>
        <label htmlFor="document-ai-label-filter">{t("Nhãn AI hiển thị")}</label>
        <p id="ai-label-filter-help" className="search-help">{t("Tùy chọn: lọc thẻ tài liệu theo nhãn AI chính xác (phân biệt hoa/thường và dấu). Khi chọn thư mục và nhãn, tài liệu phải khớp đồng thời cả hai. Không áp dụng cho kết quả tìm nội dung.")}</p>
        <div className="label-filter-controls">
          <input id="document-ai-label-filter" value={draft} maxLength={100} placeholder={t("Ví dụ: Macroeconomics")}
            aria-describedby="ai-label-filter-help" onChange={event => setDraft(event.target.value)} />
          <button className="btn" disabled={!draft.trim()}>{t("Áp dụng nhãn AI")}</button>
          <button type="button" className="btn" disabled={!label && !draft}
            onClick={() => { setDraft(''); onClear(); }}>{t("Xóa lọc nhãn AI")}</button>
          <button type="button" className="btn" disabled={!label && !draft && !hasFolder}
            onClick={() => { setDraft(''); onClearAll(); }}>{t("Xóa lọc danh sách")}</button>
        </div>
      </form>
      <p role="status" className="search-help">{label ? t("Nhãn AI: “{0}”", label) : t("Tất cả nhãn AI")} · {hasFolder ? t("Thư mục: “{0}”", folderName || t("thư mục đã chọn")) : t("Tất cả thư mục")}</p>
    </section>
  );
}
