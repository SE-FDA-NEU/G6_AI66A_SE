#!/usr/bin/env python3
"""Start DocuMind and open its UI: python run.py (Windows/macOS/Linux)."""

import argparse
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


def server_commands():
    python = ROOT / 'backend/.venv' / ('Scripts/python.exe' if WINDOWS else 'bin/python')
    node = shutil.which('node')
    next_cli = ROOT / 'frontend/node_modules/next/dist/bin/next'
    if not python.is_file():
        raise RuntimeError('Thiếu backend/.venv. Hãy cài backend theo docs/SETUP.md trước.')
    if not node or not next_cli.is_file():
        raise RuntimeError('Cần Node.js và dependencies frontend. Chạy npm ci trong thư mục frontend.')
    if not (ROOT / 'backend/.env').is_file():
        raise RuntimeError('Thiếu backend/.env. Hãy cấu hình theo docs/SETUP.md trước.')
    # Invoke Node directly: npm.cmd cannot be launched like an executable on Windows.
    return [
        ('backend', [str(python), '-m', 'uvicorn', 'app.main:app',
                     '--reload', '--host', '127.0.0.1', '--port', '8001'], {}),
        ('frontend', [node, str(next_cli), 'dev', '--hostname', '127.0.0.1', '--port', '8000'],
         {'BACKEND_ORIGIN': API_URL}),
    ]


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
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        commands = server_commands()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    for port in (8000, 8001):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                print(f'Cổng {port} đang được dùng. Dừng server cũ trước khi chạy lại.', file=sys.stderr)
                return 1

    children = []

    def stop_requested(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop_requested)
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                   if WINDOWS else {'start_new_session': True})
        print('Đang khởi động DocuMind… MySQL cần được bật để đăng nhập.', flush=True)
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
