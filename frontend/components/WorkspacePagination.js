import { ui } from '../lib/ui';
import { useI18n } from '../lib/i18n';
export default function WorkspacePagination({ label, page, hasNext, busy, onPage }) {
  const { t, locale, errorText } = useI18n();
  return (
    <nav className={ui('workspace-pagination')} aria-label={t(label)}>
      <button className={ui('btn')} disabled={busy || page === 0} onClick={() => onPage(page - 1)}>{t("Trang trước")}</button>
      <span aria-live="polite">{t("Trang") + " "}{page + 1}</span>
      <button className={ui('btn')} disabled={busy || !hasNext} onClick={() => onPage(page + 1)}>{t("Trang sau")}</button>
    </nav>
  );
}
