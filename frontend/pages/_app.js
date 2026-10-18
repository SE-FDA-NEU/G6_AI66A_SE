import { LanguageProvider, LanguageSwitcher } from '../lib/i18n';
import '../styles/globals.css';
import '../styles/library.css';
export default function App({ Component, pageProps }) {
  return <LanguageProvider initialLocale={pageProps.initialLocale}><Component {...pageProps} /><LanguageSwitcher /></LanguageProvider>;
}
