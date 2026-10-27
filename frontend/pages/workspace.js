import { readLocale } from '../lib/i18n';
import { getSession } from '../lib/session';
export { default } from '../components/WorkspaceHome';

export async function getServerSideProps({ req, res }) {
  res.setHeader('Cache-Control', 'no-store');
  const user = await getSession(req);
  return user ? { props: { user, initialLocale: readLocale(req.headers.cookie) } } : { redirect: { destination: '/', permanent: false } };
}

