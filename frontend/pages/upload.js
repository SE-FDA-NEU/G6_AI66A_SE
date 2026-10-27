import WorkflowSteps from '../components/WorkflowSteps';
import { ui } from '../lib/ui';
import { useI18n, readLocale } from '../lib/i18n';
import Head from 'next/head';
import { getSession } from '../lib/session';
import WorkspaceNavigation from '../components/WorkspaceNavigation';
import DocumentUpload from '../components/DocumentUpload';

export default function Upload() {
  const { t } = useI18n();
  return <>
    <Head><title>{t("DocuMind · Tải tài liệu")}</title></Head>
    <main className={ui('workspace upload-page')}>
      <header>
        <a href="/workspace" className={ui('brand')}>{t("DocuMind")}<span className={ui('brand-dot')}>.</span></a>
        <WorkspaceNavigation><a href="/workspace" className={ui('btn')}>{t("Về không gian tài liệu")}</a></WorkspaceNavigation>
      </header>
      <WorkflowSteps step={2}/>
      <DocumentUpload />
    </main>
  </>;
}

export async function getServerSideProps({ req, res }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  return user ? { props: { initialLocale: readLocale(req.headers.cookie) } } : { redirect: { destination: '/', permanent: false } };
}
