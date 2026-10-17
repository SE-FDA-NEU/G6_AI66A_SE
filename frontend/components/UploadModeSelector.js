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
  return (
    <div className="upload-mode-selector">
      <label htmlFor={id} className="upload-mode-label">
        Kiểu phân tích
      </label>
      <select
        id={id}
        name="mode"
        data-testid="analysis-mode-selector"
        value={value}
        disabled={disabled}
        onChange={e => onChange(e.target.value)}
        className="upload-mode-select"
      >
        <option value="bullet">Bullet Summary</option>
        <option value="table">Financial Clause Table</option>
        <option value="concept">Concept Overview</option>
      </select>
    </div>
  );
}
