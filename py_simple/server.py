from flask import Flask, jsonify, request
from flask_cors import CORS
from .safe_ransomware_simulator import SafeRansomwareSimulator
from .behavior_simulator import BehaviorSimulator
import os, json, socket, base64
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize the simulator; allow override via env var SANDBOX_DIR
simulator = SafeRansomwareSimulator(os.getenv('SANDBOX_DIR') or None)
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

@app.route('/encrypt', methods=['POST'])
def encrypt():
    """Trigger encryption of files in the target directory"""
    try:
        files = simulator.simulate_encryption()
        return jsonify({'status': 'Encryption completed successfully', 'files': files})
    except Exception as e:
        return jsonify({'status': 'Encryption failed', 'error': str(e)}), 500

@app.route('/decrypt', methods=['POST'])
def decrypt():
    """Trigger decryption of files"""
    try:
        simulator.simulate_decryption()
        return jsonify({'status': 'Decryption completed successfully'})
    except Exception as e:
        return jsonify({'status': 'Decryption failed', 'error': str(e)}), 500

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
    app.run(debug=True, port=5000)