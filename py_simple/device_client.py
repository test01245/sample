"""
Device client for the safe ransomware simulator.

Runs on the Windows VM, registers with the backend, connects over Socket.IO,
and performs encryption/decryption ONLY in the sandbox folder.

Defaults:
- Sandbox path: C:\\Users\\user\\test\\ (override with SANDBOX_DIR env var)
- Backend URL: set BACKEND_URL env var or pass --backend

Usage (PowerShell/CMD):
    pip install -r requirements.txt
    python py_simple/device_client.py --backend https://sample-2ang.onrender.com

This is a safe, reversible demo for research and lab testing.
"""
from __future__ import annotations

import argparse
import os
import socket
import time
import requests
import socketio  # python-socketio client
import sys

# Import simulator from local package
try:
    from py_simple.safe_ransomware_simulator import SafeRansomwareSimulator
except Exception:
    from safe_ransomware_simulator import SafeRansomwareSimulator


def main():
    parser = argparse.ArgumentParser(description="Device client for safe simulator")
    parser.add_argument("--backend", dest="backend", default=os.getenv("BACKEND_URL"), help="Backend base URL, e.g. https://sample-2ang.onrender.com")
    parser.add_argument("--hostname", dest="hostname", default=socket.gethostname(), help="Hostname to report to server")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification (diagnostics only)")
    parser.add_argument("--polling", action="store_true", help="Force Socket.IO polling transport (no WebSocket)")
    parser.add_argument("--debug", action="store_true", help="Enable verbose Socket.IO logging")
    parser.add_argument("--recursive", action="store_true", help="Process files in subfolders as well (or set SANDBOX_RECURSIVE=1)")
    args = parser.parse_args()

    # Allow prompting for backend when launched by double-click (set PROMPT_BACKEND=1)
    if not args.backend and os.getenv("PROMPT_BACKEND") == "1":
        try:
            entered = input("Enter backend URL (e.g., https://sample-2ang.onrender.com): ").strip()
            if entered:
                args.backend = entered
        except Exception:
            pass

    if not args.backend:
        raise SystemExit("Please provide --backend or set BACKEND_URL")

    # Ensure backend has no trailing slash
    backend = args.backend.rstrip("/")

    # Configure sandbox dir (Windows VM path by default)
    sandbox_dir = os.getenv("SANDBOX_DIR") or r"C:\\Users\\user\\test\\"
    # Recursive mode: flag or env SANDBOX_RECURSIVE=1
    recursive = args.recursive or (os.getenv("SANDBOX_RECURSIVE") == "1")
    simulator = SafeRansomwareSimulator(sandbox_dir, recursive=recursive)
    print(f"[client] Sandbox directory: {simulator.test_directory}")
    print(f"[client] Recursive mode: {'on' if simulator.recursive else 'off'}")

    # Prepare a requests session so we can control TLS verification for all HTTP calls
    session = requests.Session()
    session.verify = not args.insecure

    # Probe backend status for quick diagnostics
    try:
        s = session.get(f"{backend}/status", timeout=5)
        print(f"[client] Backend /status -> {s.status_code}")
    except Exception as e:
        print(f"[client] Backend /status probe failed: {e}")

    # Register to get a device token and public key (with retries)
    attempts, delay = 3, 2
    last_err = None
    for i in range(1, attempts + 1):
        try:
            res = session.post(
                f"{backend}/publickey",
                json={"hostname": args.hostname},
                timeout=25,
            )
            res.raise_for_status()
            data = res.json()
            device_token = data.get("device_token")
            ws_url = data.get("ws_url") or backend
            print(f"[client] Received device token: {device_token}")
            print("[client] Public key (demo):\n" + (data.get("public_key_pem") or "<none>"))
            if not device_token:
                raise RuntimeError("No device_token in response")
            break
        except Exception as e:
            last_err = e
            print(f"[client] Register attempt {i}/{attempts} failed: {e}")
            if i < attempts:
                time.sleep(delay)
                delay *= 2
    if last_err and 'device_token' not in locals():
        raise SystemExit(f"Failed to register after {attempts} attempts: {last_err}")

    # Connect to Socket.IO
    # Pass the session to Socket.IO so polling transport also uses our TLS settings
    sio = socketio.Client(
        reconnection=True,
        http_session=session,
        logger=args.debug,
        engineio_logger=args.debug,
    )

    @sio.event
    def connect():
        print("[client] Connected to server, authenticating…")
        sio.emit("authenticate", {"device_token": device_token})

    @sio.on("auth_ok")
    def on_auth_ok(msg):
        print("[client] Authenticated.")

    @sio.on("auth_error")
    def on_auth_error(msg):
        print(f"[client] Auth error: {msg}")
        sio.disconnect()

    @sio.on("encrypt")
    def on_encrypt(_msg=None):
        print("[client] Received ENCRYPT signal – starting simulation (non-destructive)…")
        try:
            files = simulator.simulate_encryption(destructive=False)
            print(f"[client] Encrypted files: {len(files)}")
        except Exception as e:
            print(f"[client] Encryption failed: {e}")

    @sio.on("decrypt")
    def on_decrypt(_msg=None):
        print("[client] Received DECRYPT signal – restoring files…")
        try:
            simulator.simulate_decryption()
            print("[client] Decryption complete")
        except Exception as e:
            print(f"[client] Decryption failed: {e}")

    @sio.event
    def disconnect():
        print("[client] Disconnected. Will try to reconnect…")

    # Socket.IO server URL (use HTTP base; client handles upgrade)
    try:
        print(f"[client] Connecting to {backend} …")
        transports = ["polling"] if args.polling else ["websocket", "polling"]
        # socketio_path default is 'socket.io' but set explicitly to avoid proxy/path issues.
        sio.connect(
            backend,
            transports=transports,
            wait_timeout=30,
            socketio_path='socket.io'
        )
    except Exception as e:
        raise SystemExit(f"Failed to connect to Socket.IO: {e!r}")

    # Keep the client alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[client] Exiting…")
        sio.disconnect()

def _run_with_optional_pause():
    """Run main() and optionally pause on exit when PAUSE_ON_EXIT=1 is set.

    Useful when double-clicking on Windows so the console doesn't close instantly.
    """
    pause = os.getenv("PAUSE_ON_EXIT") == "1"
    try:
        main()
    except SystemExit as e:
        # Print the error and pause if requested; re-raise only when not pausing so exit codes are preserved in CI/terminals
        msg = str(e) or "Exiting"
        print(f"[client] {msg}")
        if pause:
            try:
                input("Press Enter to exit…")
            except Exception:
                pass
        else:
            raise
    except Exception as e:
        print(f"[client] Unhandled error: {e}")
        if pause:
            try:
                input("Press Enter to exit…")
            except Exception:
                pass
        else:
            raise


if __name__ == "__main__":
    _run_with_optional_pause()
