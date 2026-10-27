import { ArrowRight } from 'lucide-react';
import { useI18n } from '../lib/i18n';
export default function WorkflowSteps({ step = 1 }) {
  const { t } = useI18n();
  const items = [[1, 'Thư viện', '/workspace'], [2, 'Tải tài liệu', '/upload'], [3, 'Kết quả & nguồn', null]];
  return <nav aria-label={t('Các bước làm việc')} className="border-b border-line">
    <ol className="grid grid-cols-3 divide-x divide-line">
      {items.map(([number, label, href]) => {
        const Tag = href || step >= number ? 'a' : 'span';
        return <li key={number} className="min-w-0">
        <Tag href={href || (step >= number ? '#results' : undefined)} aria-disabled={!href && step < number ? true : undefined} aria-current={step === number ? 'step' : undefined}
          className={`flex min-h-14 flex-wrap items-center gap-2 px-3 py-3 text-xs transition-colors sm:px-5 ${step === number ? 'bg-surface text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'}`}>
          <span className={`font-mono text-[10px] ${step === number ? 'text-orange-500' : ''}`}>0{number}</span>
          <span>{t(label)}</span>{step === number && <ArrowRight size={13} className="ml-auto hidden sm:block" />}
        </Tag>
      </li>; })}
    </ol>
  </nav>;
}
