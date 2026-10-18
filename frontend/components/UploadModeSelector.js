import { useI18n } from '../lib/i18n';
export const UPLOAD_MODES = [
  { value: 'bullet', label: 'Bullet Summary' },
  { value: 'table', label: 'Financial Clause Table' },
  { value: 'concept', label: 'Concept Overview' },
];

export default function UploadModeSelector({
  value,
  onChange,
  disabled = false,
  id = 'analysis-mode',
}) {
  const { t, locale, errorText } = useI18n();
  return (
    <div className="upload-mode-selector">
      <label htmlFor={id} className="upload-mode-label">{t("Kiểu phân tích")}</label>
      <select
        id={id}
        name="mode"
        data-testid="analysis-mode-selector"
        value={value}
        disabled={disabled}
        onChange={e => onChange(e.target.value)}
        className="upload-mode-select"
      >
        {UPLOAD_MODES.map(mode => (
          <option key={mode.value} value={mode.value}>{t(mode.label)}</option>
        ))}
      </select>
    </div>
  );
}
