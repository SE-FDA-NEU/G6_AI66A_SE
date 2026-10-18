#!/usr/bin/env python3
"""Start DocuMind and open its UI: python run.py (Windows/macOS/Linux)."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
UI_URL = 'http://127.0.0.1:8000'
API_URL = 'http://127.0.0.1:8001'
WINDOWS = os.name == 'nt'


def backend_python():
    return ROOT / 'backend/.venv' / ('Scripts/python.exe' if WINDOWS else 'bin/python')


def run_checked(command, *, directory=ROOT):
    try:
        subprocess.run(command, cwd=directory, check=True,
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError('Bước chuẩn bị thất bại. Xem thông báo phía trên rồi chạy lại run.py.') from error


def ensure_backend_dependencies(development=False):
    python = backend_python()
    if not python.is_file():
        if sys.version_info < (3, 11):
            raise RuntimeError('Cần Python 3.11 trở lên để tạo backend/.venv.')
        print('Đang tạo backend/.venv…', flush=True)
        run_checked([sys.executable, '-m', 'venv', str(ROOT / 'backend/.venv')])
    probe = subprocess.run([str(python), '-c',
                            'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'], check=False)
    if probe.returncode:
        raise RuntimeError('backend/.venv cần Python 3.11 trở lên. Hãy tạo lại venv bằng Python mới.')
    requirements = ROOT / 'backend' / ('requirements-dev.txt' if development else 'requirements.txt')
    # All direct requirements are pinned. Check recursively without importing any
    # third-party package, so this also works in a newly created virtualenv.
    checker = r"""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

def check(path):
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith('-r '):
            if not check(path.parent / line[3:].strip()):
                return False
            continue
        name, pin = line.split('==', 1)
        try:
            if version(name.split('[', 1)[0]) != pin:
                return False
        except PackageNotFoundError:
            return False
    return True
sys.exit(0 if check(Path(sys.argv[1])) else 1)
"""
    checked = subprocess.run([str(python), '-c', checker, str(requirements)], check=False)
    # Checking top-level pins also needs to catch missing/conflicting transitive
    # packages and extras (e.g. cryptography, uvicorn reload dependencies).
    dependencies = subprocess.run([str(python), '-m', 'pip', 'check'],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    extras = subprocess.run([str(python), '-c', 'import cryptography, watchfiles, httptools, websockets, dotenv, yaml; '
                            'import sys; '
                            'exec("import uvloop" if sys.platform != "win32" and sys.implementation.name == "cpython" else "")'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if checked.returncode or dependencies.returncode or extras.returncode:
        print(f'Đang cài/đồng bộ {requirements.relative_to(ROOT)}…', flush=True)
        run_checked([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirements)])
    run_checked([str(python), '-m', 'pip', 'check'])
    return python


def server_commands():
    python = backend_python()
    node = shutil.which('node')
    next_cli = ROOT / 'frontend/node_modules/next/dist/bin/next'
    if not python.is_file():
        raise RuntimeError('Không tìm thấy Python của backend sau bước cài đặt.')
    if not node or not next_cli.is_file():
        raise RuntimeError('Cần Node.js và dependencies frontend. Chạy npm ci trong thư mục frontend.')
    # Invoke Node directly: npm.cmd cannot be launched like an executable on Windows.
    return [
        ('backend', [str(python), '-m', 'uvicorn', 'app.main:app',
                     '--reload', '--host', '127.0.0.1', '--port', '8001'], {}),
        ('frontend', [node, str(next_cli), 'dev', '--hostname', '127.0.0.1', '--port', '8000'],
         {'BACKEND_ORIGIN': API_URL}),
    ]


def prepare_local(development=False):
    if not (ROOT / 'backend/.env').is_file():
        raise RuntimeError('Thiếu backend/.env. Sao chép backend/.env.example và điền cấu hình MySQL trước.')
    node = shutil.which('node')
    npm = shutil.which('npm.cmd' if WINDOWS else 'npm')
    if not node or not npm:
        raise RuntimeError('Cần Node.js 20.9 trở lên và npm để chạy frontend.')
    result = subprocess.run([node, '-p', 'JSON.stringify(process.versions.node)'],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError('Không đọc được phiên bản Node.js.')
    version = tuple(int(part) for part in json.loads(result.stdout).split('.')[:2])
    if version < (20, 9):
        raise RuntimeError('Cần Node.js 20.9 trở lên để chạy Next.js.')
    python = ensure_backend_dependencies(development)
    if not (ROOT / 'frontend/node_modules/next/dist/bin/next').is_file():
        print('Đang cài frontend bằng npm ci…', flush=True)
        # npm.cmd is a Windows command script; use cmd.exe explicitly.
        command = ([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', npm, 'ci']
                   if WINDOWS else [npm, 'ci'])
        run_checked(command, directory=ROOT / 'frontend')
    print('Đang kiểm tra database MySQL và các bảng…', flush=True)
    run_checked([str(python), '-m', 'app.db.bootstrap'], directory=ROOT / 'backend')


def wait_ready(children, timeout=120):
    pending = {API_URL, UI_URL}
    deadline = time.monotonic() + timeout
    while pending and time.monotonic() < deadline:
        if any(child.poll() is not None for child in children):
            raise RuntimeError('Một server đã thoát trong khi khởi động. Xem lỗi ở terminal phía trên.')
        for url in tuple(pending):
            try:
                with urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        pending.remove(url)
            except (URLError, TimeoutError, OSError):
                pass
        if pending:
            time.sleep(0.25)
    if pending:
        raise RuntimeError('Server chưa sẵn sàng sau 120 giây. Xem lỗi khởi động ở terminal phía trên.')


def stop_servers(children):
    if WINDOWS:
        # Kill only trees started by this launcher, including reload/Next children.
        for child in children:
            if child.poll() is None:
                subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        for child in children:
            child.wait()
        return
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    for child in children:
        try:
            child.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def main():
    parser = argparse.ArgumentParser(description='Khởi động DocuMind và tự mở giao diện.')
    parser.add_argument('--no-browser', action='store_true', help='Chạy server mà không tự mở trình duyệt')
    parser.add_argument('--setup-only', action='store_true', help='Cài dependencies và đồng bộ database rồi thoát')
    parser.add_argument('--dev', action='store_true', help='Cài thêm requirements-dev.txt để chạy kiểm thử backend')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    for port in (8000, 8001):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                print(f'Cổng {port} đang được dùng. Dừng server cũ trước khi chạy lại.', file=sys.stderr)
                return 1

    try:
        prepare_local(args.dev)
        if args.setup_only:
            print('Đã chuẩn bị xong môi trường và database.', flush=True)
            return 0
        commands = server_commands()
    except KeyboardInterrupt:
        print('\nĐã dừng bước chuẩn bị.', flush=True)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f'Không thể chuẩn bị DocuMind: {error}', file=sys.stderr)
        return 1

    children = []

    def stop_requested(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop_requested)
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                   if WINDOWS else {'start_new_session': True})
        print('Database đã sẵn sàng. Đang khởi động DocuMind…', flush=True)
        for directory, command, env in commands:
            children.append(subprocess.Popen(
                command, cwd=ROOT / directory,
                env={**os.environ, **env, 'PYTHONIOENCODING': 'utf-8'}, **options,
            ))
        wait_ready(children)
        print(f'UI sẵn sàng: {UI_URL}', flush=True)
        print(f'Swagger: {API_URL}/docs', flush=True)
        print('Nhấn Ctrl+C để dừng cả hai server.', flush=True)
        if not args.no_browser and not webbrowser.open(UI_URL, new=2):
            print(f'Không thể tự mở trình duyệt. Hãy mở {UI_URL}', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.25)
        print('Một server đã thoát; đang dừng server còn lại.', flush=True)
        return 1
    except KeyboardInterrupt:
        print('\nĐang dừng cả hai server...', flush=True)
        return 0
    except (OSError, RuntimeError) as error:
        print(f'Không thể chạy DocuMind: {error}', file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        stop_servers(children)


if __name__ == '__main__':
    sys.exit(main())
