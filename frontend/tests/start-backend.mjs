import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../../', import.meta.url));
const localPython = path.join(root, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.E2E_PYTHON || (existsSync(localPython) ? localPython : 'python');
const child = spawn(python, [path.join(root, 'backend/test/serve_auth_e2e.py')], {
  cwd: path.join(root, 'backend'), stdio: 'inherit',
  env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
});
child.on('error', error => { console.error(`Cannot start E2E backend: ${error.message}`); process.exit(1); });
child.on('exit', code => process.exit(code ?? 1));
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => { child.kill(signal); });
}
