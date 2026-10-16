#!/usr/bin/env python3
"""Start both local development servers: python3 run.py (macOS/Linux)."""

import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def main():
    python = ROOT / 'backend/.venv/Scripts/python.exe'
    npm = shutil.which('npm')
    if not python.is_file():
        sys.exit('Thiếu backend/.venv. Hãy cài backend theo docs/SETUP.md trước.')
    if not npm or not (ROOT / 'frontend/node_modules/.bin/next').is_file():
        sys.exit('Cần Node.js và dependencies frontend. Chạy: cd frontend && npm ci')
    if not (ROOT / 'backend/.env').is_file():
        sys.exit('Thiếu backend/.env. Hãy cấu hình theo docs/SETUP.md trước.')

    for port in (8000, 8001):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                sys.exit(f'Cổng {port} đang được dùng. Dừng server cũ trước khi chạy lại.')

    children = []

    def stop_requested(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop_requested)
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        commands = [
            ('backend', [str(python), '-m', 'uvicorn', 'app.main:app',
                         '--reload', '--host', '127.0.0.1', '--port', '8001'], {}),
            ('frontend', [npm, 'run', 'dev'], {'BACKEND_ORIGIN': 'http://127.0.0.1:8001'}),
        ]
        for directory, command, env in commands:
            children.append(subprocess.Popen(
                command, cwd=ROOT / directory, env={**os.environ, **env},
                start_new_session=True,
            ))
        print('Đang khởi động frontend: http://127.0.0.1:8000', flush=True)
        print('Swagger: http://127.0.0.1:8001/docs', flush=True)
        print('MySQL cần được bật sẵn. Nhấn Ctrl+C để dừng cả hai server.', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.25)
        print('Một server đã thoát; đang dừng server còn lại.', flush=True)
        return 1
    except KeyboardInterrupt:
        print('\nĐang dừng cả hai server...', flush=True)
        return 0
    finally:
        # Each server has its own group, including npm/Next and Uvicorn reload children.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
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


if __name__ == '__main__':
    sys.exit(main())
