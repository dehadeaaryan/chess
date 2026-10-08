"""Run the Python API and Svelte development server together: python3 dev.py."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import json

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def main():
    if not PYTHON.exists() or not shutil.which('bun') or not (ROOT / 'web/node_modules').exists():
        sys.exit("Install dependencies first (see README.md): create .venv, pip install -e '.[test]', and run bun install in web/.")
    children = []
    try:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2) as response:
                api_running = json.load(response) == {'status': 'ok'}
        except (OSError, ValueError):
            api_running = False
        if api_running:
            print('Using the running chess API on port 8000.', flush=True)
        else:
            children.append(subprocess.Popen([str(PYTHON), '-m', 'uvicorn', 'chess_game.api:app', '--host', '127.0.0.1', '--port', '8000', '--reload'], cwd=ROOT))
        children.append(subprocess.Popen(['bun', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort'], cwd=ROOT / 'web'))
        print('\nChess: http://localhost:5173 · Leave this terminal open. Ctrl+C stops servers started here.\n', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.3)
        sys.exit('A development server stopped. Check the messages above; ports 8000 and 5173 must be available.')
    except KeyboardInterrupt:
        print('\nStopping chess servers.', flush=True)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    main()
