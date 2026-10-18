import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { LOCALE_COOKIE, readLocale, translate, isLocalizedMessage } from './i18n-core';

const LocaleContext = createContext(null);
export function LanguageProvider({ initialLocale, children }) {
  const [locale, setLocale] = useState(initialLocale === 'en' ? 'en' : 'vi');
  useEffect(() => { if (initialLocale == null) setLocale(readLocale(document.cookie)); }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.cookie = `${LOCALE_COOKIE}=${locale}; Path=/; Max-Age=31536000; SameSite=Lax`;
  }, [locale]);
  const t = useCallback((message, ...values) => translate(locale, message, ...values), [locale]);
  const value = useMemo(() => ({ locale, setLocale, t }), [locale, t]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
export function useI18n() {
  const context = useContext(LocaleContext);
  if (!context) throw new Error('LanguageProvider is required.');
  const errorText = (message) => {
    if (typeof message !== 'string') return context.t('Không thể hoàn tất thao tác. Vui lòng thử lại.');
    if (/incorrect|invalid credentials|wrong password/i.test(message)) return context.t('Sai email hoặc mật khẩu.');
    const localized = context.t(message);
    if (isLocalizedMessage(message)) return localized;
    if (/source_expired/i.test(message)) return context.t('Nguồn đã hết hạn và không còn khả dụng.');
    // Unknown server details may contain provider English; show a complete localized error.
    return context.t('Không thể hoàn tất thao tác. Vui lòng thử lại.');
  };
  return { ...context, errorText };
}
export function languageHeaders(locale) { return { 'X-DocuMind-Language': locale }; }
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();
  return <div className="language-switcher"><label htmlFor="app-language">{t('Ngôn ngữ')}</label><select id="app-language" value={locale} onChange={event => setLocale(event.target.value)}>
    <option value="vi">{t('Tiếng Việt')}</option><option value="en">{t('Tiếng Anh')}</option>
  </select></div>;
}
export { readLocale };
