import { useState } from 'react';
import { FileText, List, Table2, Tags, ScanText, FolderOpen, ArrowUpRight, Terminal, Check } from 'lucide-react';
import { useI18n } from '../lib/i18n';

const modules = [
  [FileText, 'Tài liệu, sẵn sàng để đọc', 'Nhận PDF, DOCX và PPTX. Văn bản được giữ theo trang hoặc slide cùng vị trí nguồn để bạn có thể đối chiếu.'],
  [List, 'Tóm tắt đúng trọng tâm', 'Đọc các ý chính và hành động đề xuất thay cho toàn bộ tài liệu. Mỗi nội dung có nguồn riêng để kiểm tra.'],
  [Table2, 'Điều khoản, đặt cạnh nhau', 'Xem giá trị, lịch thanh toán và điều khoản phạt trong bảng so sánh. Thông tin không có trong nguồn được đánh dấu rõ.'],
  [Tags, 'Nhãn AI, quyết định của bạn', 'AI gợi ý nhãn và mức độ tin cậy. Bạn có thể giữ nhãn đó hoặc sửa lại, rồi tự chọn thư mục lưu tài liệu.'],
  [ScanText, 'Từ kết quả về đúng nguồn', 'Bấm vào trích dẫn để mở đúng trang gốc và xem đoạn chữ liên quan. Ý chưa đủ bằng chứng sẽ được đánh dấu để bạn kiểm tra thêm.'],
  [FolderOpen, 'Tìm lại thay vì đọc lại', 'Sắp xếp thư mục, tìm tên tệp hoặc tìm trong nội dung. Kết quả đã lưu vẫn có thể mở lại khi quay về thư viện.'],
];
const tabs = ['SUMMARY', 'CLAUSES', 'CONCEPTS', 'SOURCES'];
const tabLabels = ['Tóm tắt', 'Điều khoản', 'Khái niệm', 'Nguồn trích dẫn'];

export default function ProductOverview() {
  const { t, locale } = useI18n();
  const [active, setActive] = useState(0);
  return <>
    <section id="modules" className="border-b border-line">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-6 py-8">
        <p className="font-mono text-[10px] uppercase tracking-[.2em] text-zinc-500">02 // DOCUMENT_MODULES</p>
        <h2>{t('Một luồng làm việc, từ tệp đến thông tin.')}</h2>
      </div>
      <div className="grid grid-cols-1 gap-px bg-line md:grid-cols-2 lg:grid-cols-3">
        {modules.map(([Icon, title, description], index) => <article key={title} className="bg-canvas p-6 transition-colors hover:bg-surface">
          <div className="mb-7 flex items-center justify-between font-mono text-xs text-zinc-600"><span>0{index + 1}</span><Icon size={21} className="text-zinc-400" strokeWidth={1.5}/></div>
          <h3 className="mb-3">{t(title)}</h3><p className="text-sm leading-7 text-zinc-400">{t(description)}</p>
        </article>)}
      </div>
    </section>
    <section id="preview" className="border-b border-line">
      <div className="space-y-3 border-b border-line px-6 py-8">
        <p className="font-mono text-[10px] uppercase tracking-[.2em] text-zinc-500">03 // WORKSPACE_PREVIEW</p>
        <h2>{t('Biết bạn sẽ nhận được gì.')}</h2>
        <p className="text-sm text-zinc-500">{t('Ví dụ minh họa — không phải dữ liệu tài liệu của bạn.')}</p>
      </div>
      <div className="grid md:grid-cols-[1fr_4fr]">
        <div role="tablist" aria-label={t('Xem trước các chế độ')} className="grid grid-cols-2 border-b border-line p-3 md:flex md:flex-col md:border-r md:border-b-0">
          {tabs.map((tab, index) => <button key={tab} id={`preview-tab-${index}`} role="tab" aria-selected={active === index} aria-controls="preview-panel" tabIndex={active === index ? 0 : -1}
            onClick={() => setActive(index)} onKeyDown={event => {
              const delta = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
              if (!delta) return;
              event.preventDefault(); const next = (active + delta + tabs.length) % tabs.length; setActive(next);
              document.getElementById(`preview-tab-${next}`)?.focus();
            }} className={`min-h-12 px-3 text-left font-mono text-[10px] tracking-wider ${active === index ? 'bg-hover text-orange-500' : 'text-zinc-500 hover:text-zinc-200'}`}>
              <span className="mr-2 text-zinc-600">0{index + 1}</span><span className="sr-only">[{tab}] </span>{t(tabLabels[index])}
            </button>)}
        </div>
        <div id="preview-panel" role="tabpanel" aria-labelledby={`preview-tab-${active}`} tabIndex={0} className="min-h-72 space-y-5 bg-surface p-5 sm:p-8">
          <div className="flex items-center gap-2 font-mono text-[10px] text-zinc-500"><Terminal size={13}/><span>service_contract.pdf / {tabs[active].toLowerCase()}</span><span className="ml-auto text-orange-400">DEMO</span></div>
          {active === 0 && <><h3>{t('Tóm tắt gạch đầu dòng')}</h3><ul className="space-y-4 text-sm text-zinc-300">
            {[['Giá trị hợp đồng: 120.000.000 VND.', '02'], ['Thanh toán trong 30 ngày sau nghiệm thu.', '04'], ['Phạt chậm thanh toán: 0,05% mỗi ngày.', '05']].map(([text, page]) => <li key={page} className="flex items-start gap-3"><Check size={15} className="mt-1 text-emerald-500"/><span>{t(text)}<span className="ml-3 font-mono text-[10px] text-zinc-500">/ p.{page}</span></span></li>)}
          </ul></>}
          {active === 1 && <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="font-mono text-[10px] text-zinc-500"><tr><th className="border-b border-line py-3">{t('Nội dung')}</th><th className="border-b border-line py-3">{t('Kết quả')}</th></tr></thead><tbody className="divide-y divide-line"><tr><td className="py-4">{t('Giá trị')}</td><td>120.000.000 VND</td></tr><tr><td className="py-4">{t('Thanh toán')}</td><td>{t('30 ngày sau nghiệm thu')}</td></tr><tr><td className="py-4">{t('Phạt')}</td><td>0,05% / {t('ngày')}</td></tr></tbody></table></div>}
          {active === 2 && <div className="grid gap-5 sm:grid-cols-2">{['Phạm vi dịch vụ', 'Nghiệm thu', 'Nghĩa vụ thanh toán', 'Trách nhiệm hợp đồng'].map((text, index) => <div key={text} className="border-l border-line pl-4"><p className="mb-2 font-mono text-[10px] text-zinc-500">CONCEPT_0{index + 1}</p><h3>{t(text)}</h3></div>)}</div>}
          {active === 3 && <><p className="text-sm text-zinc-300">{t('Nguồn của thông tin, luôn đi cùng kết quả.')}</p><pre className="overflow-x-auto font-mono text-xs leading-7 text-emerald-400">{'{\n  "document": "service_contract.pdf",\n  "page": 5,\n  "span": [120, 164],\n  "verification": "source_matched"\n}'}</pre></>}
        </div>
      </div>
    </section>
    <footer>
      <div className="grid grid-cols-2 gap-px bg-line md:grid-cols-4">
        {[['DOCUMIND', 'Đọc ít hơn. Hiểu nhiều hơn.', '#login'], ['01 / LIBRARY', 'Không gian tài liệu', '#login'], ['02 / WORKFLOW', 'Khám phá tính năng', '#modules'], ['03 / PREVIEW', 'Xem kết quả mẫu', '#preview']].map(([label, text, href]) => <div key={label} className="space-y-3 bg-canvas p-6"><p className="font-mono text-[10px] tracking-wider text-zinc-600">{label}</p><a href={href} className="inline-flex items-center gap-2 text-xs text-zinc-400 hover:text-white">{t(text)}<ArrowUpRight size={12}/></a></div>)}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-6 py-4 font-mono text-[9px] text-zinc-600"><span>© 2026 DOCUMIND // ALL RIGHTS RESERVED</span><span>PDF · DOCX · PPTX // {locale.toUpperCase()}</span></div>
    </footer>
  </>;
}
