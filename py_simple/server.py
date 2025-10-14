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

from flask import Flask, jsonify, request
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
import os, json, socket, base64
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
            'public_key_fingerprint_sha256': pub_hash,
            'private_key_fingerprint_sha256': prv_hash,
            'device': record,
        })
    except Exception as e:
        return jsonify({'error': 'rsa_keygen_failed', 'message': str(e)}), 500

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

@app.route('/decrypt', methods=['POST'])
def decrypt():
    """Trigger decryption of files.
    If devices are connected via WebSocket, emit a decrypt signal to them.
    Otherwise, perform local simulator decryption as a fallback.
    """
    try:
        payload = request.get_json(silent=True) or {}
        private_key_pem = payload.get('private_key_pem')
        # Prefer a broadcast to all connected clients in this process, optionally passing a private key.
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
                'public_key_pem': info.get('public_key_pem')
            })
        return jsonify({'count': len(out), 'devices': out})
    except Exception as e:
        return jsonify({'error': 'inspect_failed', 'message': str(e)}), 500

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

@app.route('/behavior/notes', methods=['POST'])
def behavior_notes():
    files = behavior.drop_ransom_notes()
    return jsonify({'status': 'ok', 'files': files})

@app.route('/behavior/registry', methods=['POST'])
def behavior_registry():
    result = behavior.simulate_registry_changes()
    return jsonify(result)

@app.route('/behavior/registry/cleanup', methods=['POST'])
def behavior_registry_cleanup():
    result = behavior.cleanup_registry()
    return jsonify(result)

@app.route('/behavior/network', methods=['POST'])
def behavior_network():
    result = behavior.simulate_network_activity()
    return jsonify(result)

@app.route('/behavior/discovery', methods=['POST'])
def behavior_discovery():
    result = behavior.simulate_discovery()
    return jsonify(result)

@app.route('/behavior/commands', methods=['POST'])
def behavior_commands():
    path = behavior.simulate_command_strings()
    return jsonify({'status': 'ok', 'file': path})

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
    """Site triggers decrypt broadcast, optionally carrying a private key."""
    try:
        private_key_pem = (data or {}).get('private_key_pem')
        payload = {'private_key_pem': private_key_pem} if private_key_pem else None
        socketio.emit('decrypt', payload, broadcast=True)
        emit('server_ack', {'status': 'ok'})
    except Exception as e:
        emit('server_ack', {'status': 'error', 'message': str(e)})