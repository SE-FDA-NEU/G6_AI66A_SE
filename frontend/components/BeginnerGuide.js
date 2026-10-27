import { useEffect, useId, useState } from 'react';
import { ArrowRight, CircleHelp, FileUp, ListChecks, ScanText } from 'lucide-react';
import { useI18n } from '../lib/i18n';
import { ui } from '../lib/ui';

const guides = {
  workspace: {
    title: 'Lần đầu dùng DocuMind? Bắt đầu từ đây.',
    intro: 'Bạn chỉ cần một tài liệu. Chưa cần tạo thư mục hay đặt nhãn.',
    steps: [
      ['Tải một tài liệu', 'Bấm “Tải tài liệu”, chọn PDF, Word hoặc PowerPoint của bạn.'],
      ['Chọn cách đọc', 'Chưa biết chọn gì? Dùng “Tóm tắt điểm chính” để đọc nhanh trước.'],
      ['Đọc và kiểm tra', 'Đợi xử lý xong, đọc kết quả rồi bấm trích dẫn để xem đoạn gốc.'],
    ],
    action: 'Bắt đầu với tài liệu đầu tiên', href: '/upload',
  },
  upload: {
    title: 'Bạn muốn hiểu gì từ tài liệu này?',
    intro: 'Chọn tệp bên trên, chọn kiểu phân tích rồi bấm “Tải lên và phân tích”.',
    steps: [
      ['Đọc nhanh', 'Tóm tắt điểm chính: xem ý chính và việc cần làm. Phù hợp để bắt đầu.'],
      ['So sánh hợp đồng', 'Bảng điều khoản tài chính: so sánh giá trị, thanh toán và mức phạt.'],
      ['Học và nghiên cứu', 'Tổng quan khái niệm: xem các khái niệm quan trọng và lời giải thích.'],
    ],
  },
  results: {
    title: 'Đọc kết quả theo ba bước đơn giản.',
    intro: 'Trang này tự cập nhật khi tài liệu đang được xử lý. Bạn không cần gửi lại tệp.',
    steps: [
      ['Đợi trạng thái Hoàn tất', 'Thanh tiến độ cho biết số tệp đã xử lý. Nếu có lỗi, xem thông báo ở từng tệp.'],
      ['Đọc phần kết quả', 'Bấm “Đọc kết quả” để tới bản tóm tắt, bảng so sánh hoặc các khái niệm.'],
      ['Kiểm tra bằng chứng', 'Bấm tên tài liệu và số trang cạnh một ý để xem nguồn. “Chưa xác thực” nghĩa là ý đó cần được kiểm tra thêm.'],
    ],
  },
  reader: {
    title: 'Bạn đang xem tài liệu gốc để đối chiếu.',
    intro: 'Dùng Trước / Sau để đổi trang hoặc tìm một từ, câu hay điều khoản trong tài liệu.',
    steps: [
      ['Xem đoạn được dẫn', 'Nếu mở từ trích dẫn, trang nguồn và đoạn liên quan được chọn sẵn khi có thể định vị.'],
      ['Xem lại ý chính', 'Bản tóm tắt đã lưu nằm bên dưới trình đọc. Bạn có thể vừa đọc vừa đối chiếu.'],
      ['Quay về công việc', 'Dùng “Về kết quả” để xem lại phân tích hoặc “Về thư viện” để mở tài liệu khác.'],
    ],
  },
};
const icons = [FileUp, ListChecks, ScanText];

export default function BeginnerGuide({ context = 'workspace' }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(true);
  const id = useId();
  const guide = guides[context] || guides.workspace;
  const key = `documind-guide-${context}-v1`;
  useEffect(() => {
    try { setOpen(localStorage.getItem(key) !== 'hidden'); } catch {}
  }, [key]);
  function toggle() {
    try { localStorage.setItem(key, open ? 'hidden' : 'open'); } catch {}
    setOpen(!open);
  }
  return <section aria-label={t('Hướng dẫn sử dụng trang này')} className="my-5 border border-line bg-surface">
    <div className="flex flex-wrap items-center justify-between gap-3 p-4 sm:p-5">
      <div className="flex min-w-0 items-center gap-3"><CircleHelp size={18} className="text-orange-400"/>
        <h2 className="text-sm font-medium sm:text-base">{t(open ? guide.title : 'Cần trợ giúp? Xem cách sử dụng trang này.')}</h2>
      </div>
      <button type="button" className={ui('btn shrink-0')} aria-expanded={open} aria-controls={id} onClick={toggle}>
        {t(open ? 'Ẩn hướng dẫn' : 'Mở hướng dẫn')}
      </button>
    </div>
    <div id={id} hidden={!open} className="border-t border-line">
      <p className="px-4 pt-4 text-sm leading-7 text-zinc-300 sm:px-5">{t(guide.intro)}</p>
      <div className="grid gap-5 p-4 sm:grid-cols-3 sm:p-5">
        {guide.steps.map(([title, description], index) => {
          const Icon = icons[index];
          return <div key={title} className="min-w-0 border-l border-line pl-4">
            <div className="mb-2 flex items-center gap-2"><span className="font-mono text-xs text-orange-400">0{index + 1}</span><Icon size={14} className="text-zinc-500"/></div>
            <h3 className="text-sm font-medium">{t(title)}</h3><p className="mt-2 text-xs leading-6 text-zinc-400">{t(description)}</p>
          </div>;
        })}
      </div>
      {guide.href && <div className="border-t border-line p-4 sm:px-5"><a href={guide.href} className={ui('btn primary')}>{t(guide.action)}<ArrowRight size={15}/></a></div>}
    </div>
  </section>;
}
