"""Check the real Git-index guard without touching the developer's index."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('artifact', [
    '.tmp-us04-tests/generated.pdf',
    'backend/test-results/report.xml',
    'backend/.pytest_cache/cache/nodeids',
    'backend/tests/__pycache__/generated.pyc',
])
def test_guard_rejects_generated_files_even_when_force_added(tmp_path, artifact):
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'GIT_INDEX_FILE': str(tmp_path / 'isolated-index')}
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()
    git('read-tree', 'HEAD')
    blob = git('rev-parse', 'HEAD:README.md')
    git('update-index', '--add', '--cacheinfo', f'100644,{blob},{artifact}')
    result = subprocess.run([sys.executable, 'scripts/check_repository_hygiene.py'],
                            cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert artifact in result.stdout


def test_guard_accepts_current_source_and_intentional_pdf_fixtures():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, 'scripts/check_repository_hygiene.py'],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
