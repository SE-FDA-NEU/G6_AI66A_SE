import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
import { List, Table2, Network, Check } from 'lucide-react';
export const UPLOAD_MODES = [
  { value: 'bullet', label: 'Bullet Summary' },
  { value: 'table', label: 'Financial Clause Table' },
  { value: 'concept', label: 'Concept Overview' },
];
const descriptions = {
  bullet: 'Dành cho đọc nhanh: nhận các ý chính và hành động đề xuất, kèm nguồn để kiểm tra.',
  table: 'Dành cho hợp đồng: đặt giá trị, thanh toán và điều khoản phạt của các tệp cạnh nhau.',
  concept: 'Dành cho học tập và nghiên cứu: làm rõ các khái niệm cốt lõi và nguồn giải thích.',
};

export default function UploadModeSelector({
  value,
  onChange,
  disabled = false,
  id = 'analysis-mode',
  variant = 'select',
}) {
  const { t, locale, errorText } = useI18n();
  if (variant === 'cards') return <fieldset className="space-y-3">
    <legend className="mb-3 text-xs font-medium text-zinc-400">{t('Kiểu phân tích')}</legend>
    <div className="grid gap-px border border-line bg-line sm:grid-cols-3">
      {[[List, 'bullet', 'Đọc nhanh ý chính'], [Table2, 'table', 'So sánh điều khoản'], [Network, 'concept', 'Hiểu các khái niệm']].map(([Icon, mode, label]) =>
        <button key={mode} type="button" disabled={disabled} aria-pressed={value === mode} aria-describedby={`${id}-help`} className="flex min-h-16 items-center gap-3 bg-canvas px-4 py-4 text-left text-xs text-zinc-400 aria-pressed:text-white" onClick={() => onChange(mode)}><Icon size={16} className={value === mode ? 'text-orange-400' : ''}/>{t(label)}{value === mode && <Check size={13} className="ml-auto text-orange-400"/>}</button>)}
    </div>
    <p id={`${id}-help`} className="text-xs leading-6 text-zinc-500" aria-live="polite">{t(descriptions[value] || descriptions.bullet)}</p>
  </fieldset>;
  return (
    <div className={ui('upload-mode-selector')}>
      <label htmlFor={id} className={ui('upload-mode-label')}>{t("Kiểu phân tích")}</label>
      <select
        id={id}
        name="mode"
        data-testid="analysis-mode-selector"
        value={value}
        disabled={disabled}
        onChange={e => onChange(e.target.value)}
        className={ui('upload-mode-select')}
        aria-describedby={`${id}-help`}
      >
        {UPLOAD_MODES.map(mode => (
          <option key={mode.value} value={mode.value}>{t(mode.label)}</option>
        ))}
      </select>
      <p id={`${id}-help`} className="border-l-2 border-orange-500 pl-3 text-sm leading-7 text-zinc-400" aria-live="polite">{t(descriptions[value] || descriptions.bullet)}</p>
    </div>
  );
}
