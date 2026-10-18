import { useI18n } from '../lib/i18n';
export default function NotFound() {
  const { t } = useI18n();
  return <main className="workspace"><h1>{t('Không tìm thấy trang')}</h1><p>{t('Trang bạn yêu cầu không tồn tại.')}</p><a className="btn" href="/">{t('Về trang chủ')}</a></main>;
}
