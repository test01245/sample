from flask import Flask, jsonify, request
from flask_cors import CORS
from safe_ransomware_simulator import SafeRansomwareSimulator
from behavior_simulator import BehaviorSimulator

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize the simulator
simulator = SafeRansomwareSimulator()
behavior = BehaviorSimulator(simulator.test_directory)

@app.route('/key', methods=['GET'])
def get_key():
    """Return the encryption key"""
    return jsonify({'key': simulator.get_key()})

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