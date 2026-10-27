import { LanguageProvider, LanguageSwitcher } from '../lib/i18n';
import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import '../styles/tailwind.css';
export default function App({ Component, pageProps }) {
  return <LanguageProvider initialLocale={pageProps.initialLocale}><LanguageSwitcher /><Component {...pageProps} /></LanguageProvider>;
}
