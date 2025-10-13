"""
Device client for the safe ransomware simulator.

Runs on the Windows VM, registers with the backend, connects over Socket.IO,
and performs encryption/decryption ONLY in the sandbox folder.

Defaults:
- Sandbox path: C:\\Users\\user\\test\\ (override with SANDBOX_DIR env var)
- Backend URL: set BACKEND_URL env var or pass --backend

Usage (PowerShell/CMD):
  pip install -r requirements.txt
  python py_simple/device_client.py --backend https://<render-app>.onrender.com

This is a safe, reversible demo for research and lab testing.
"""
from __future__ import annotations

import argparse
import os
import socket
import time
import requests
import socketio  # python-socketio client

# Import simulator from local package
try:
    from py_simple.safe_ransomware_simulator import SafeRansomwareSimulator
except Exception:
    from safe_ransomware_simulator import SafeRansomwareSimulator


def main():
    parser = argparse.ArgumentParser(description="Device client for safe simulator")
    parser.add_argument("--backend", dest="backend", default=os.getenv("BACKEND_URL"), help="Backend base URL, e.g. https://app.onrender.com")
    parser.add_argument("--hostname", dest="hostname", default=socket.gethostname(), help="Hostname to report to server")
    args = parser.parse_args()

    if not args.backend:
        raise SystemExit("Please provide --backend or set BACKEND_URL")

    # Ensure backend has no trailing slash
    backend = args.backend.rstrip("/")

    # Configure sandbox dir (Windows VM path by default)
    sandbox_dir = os.getenv("SANDBOX_DIR") or r"C:\\Users\\user\\test\\"
    simulator = SafeRansomwareSimulator(sandbox_dir)
    print(f"[client] Sandbox directory: {simulator.test_directory}")

    # Register to get a device token and public key
    try:
        res = requests.post(f"{backend}/publickey", json={"hostname": args.hostname}, timeout=10)
        res.raise_for_status()
        data = res.json()
        device_token = data.get("device_token")
        ws_url = data.get("ws_url") or backend
        print(f"[client] Received device token: {device_token}")
        print("[client] Public key (demo):\n" + (data.get("public_key_pem") or "<none>"))
        if not device_token:
            raise RuntimeError("No device_token in response")
    except Exception as e:
        raise SystemExit(f"Failed to register: {e}")

    # Connect to Socket.IO
    sio = socketio.Client(reconnection=True)

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
        sio.connect(backend, transports=["websocket", "polling"], wait_timeout=10)
    except Exception as e:
        raise SystemExit(f"Failed to connect to Socket.IO: {e}")

    # Keep the client alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[client] Exiting…")
        sio.disconnect()


if __name__ == "__main__":
    main()
