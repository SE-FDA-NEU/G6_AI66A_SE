import { useI18n } from '../lib/i18n';
import { useEffect, useState } from 'react';

const WEEK = 7 * 24 * 60 * 60 * 1000;

export default function DocumentExpiry({ expiresAt }) {
  const { t, locale, errorText } = useI18n();
  const [now, setNow] = useState(null);
  // The API's naive timestamps are UTC, not the browser's local time zone.
  const value = typeof expiresAt === 'string' ? expiresAt.trim() : '';
  const timestamp = value ? Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`) : NaN;
  const valid = Number.isFinite(timestamp);
  useEffect(() => {
    let timer;
    function update() {
      const time = Date.now();
      setNow(time);
      const boundary = valid ? (time < timestamp - WEEK ? timestamp - WEEK : timestamp) : Infinity;
      timer = setTimeout(update, Math.max(1, Math.min(60000, boundary > time ? boundary - time : 60000)));
    }
    update();
    return () => clearTimeout(timer);
  }, [timestamp, valid]);
  const expired = valid && now !== null && now >= timestamp;
  const soon = valid && now !== null && !expired && now >= timestamp - WEEK;
  return <div className="document-expiry" data-testid="document-expiry" aria-live="polite">
    {valid ? <span>{t("Hết hạn:") + " "}<time dateTime={new Date(timestamp).toISOString()}>
      {new Intl.DateTimeFormat(locale === 'en' ? 'en-GB' : 'vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' }).format(timestamp)}
    </time>{" " + t("(UTC)")}</span> : <span>{t("Chưa có ngày hết hạn.")}</span>}
    {soon && <span className="expiry-warning" data-testid="expiry-warning">{t("Sắp hết hạn · Còn tối đa 7 ngày. Mở, tải hoặc cập nhật tài liệu để gia hạn 30 ngày.")}</span>}
    {expired && <span className="expiry-warning" data-testid="expiry-elapsed">{t("Đã tới hạn lưu. Nguồn có thể đã được xóa; hãy mở tài liệu để kiểm tra khả dụng.")}</span>}
  </div>;
}
