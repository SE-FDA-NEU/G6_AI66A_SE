"""Reject generated test artifacts in the Git index (also used by CI)."""
import argparse
import subprocess
import sys
from pathlib import PurePosixPath


def generated(path):
    parts = PurePosixPath(path).parts
    return any(
        part.startswith('.tmp') or part in {
            '.pytest_cache', '__pycache__', 'test-results', 'playwright-report',
            'htmlcov', '.venv', 'node_modules',
        }
        for part in parts
    ) or PurePosixPath(path).name in {'.coverage', 'coverage.xml'} or path.endswith(('.pyc', '.pyo'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', help='Check a committed tree instead of the Git index')
    args = parser.parse_args()
    command = (['git', 'ls-tree', '-r', '--name-only', '-z', args.revision]
               if args.revision else ['git', 'ls-files', '-z'])
    result = subprocess.run(
        command, check=True, stdout=subprocess.PIPE,
    )
    paths = result.stdout.decode('utf-8', errors='surrogateescape').split('\0')
    blocked = sorted(path for path in paths if path and generated(path))
    if blocked:
        print('Generated artifacts must not be committed:')
        print('\n'.join(blocked))
        print('Unstage/untrack these files and keep runtime output outside source folders.')
        return 1
    print('Repository hygiene: no generated test artifacts tracked.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
