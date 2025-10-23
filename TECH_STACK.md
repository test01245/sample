# 🏗️ Complete Tech Stack & Architecture Map

## Project Overview
**C2 Command & Control Ransomware Lab Simulator**
- Safe educational ransomware simulation
- Real-time device management
- Encrypted key storage with Supabase
- WebSocket-based command execution

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                               │
├─────────────────────────────────────────────────────────────────────┤
│  Technology: React 19 + Vite                                        │
│  UI: EliteUI.jsx (Modern Glassmorphism Design)                      │
│  ├─ Real-time Socket.IO client                                      │
│  ├─ Supabase direct connection                                      │
│  └─ REST API calls to backend                                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Supabase   │  │   Backend    │  │  Static CDN  │
│   Database   │  │  Flask API   │  │   (Vercel)   │
└──────────────┘  └──────┬───────┘  └──────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Python       │  │ Go Socket    │  │ Ransomware   │
│ Device Client│  │ Client       │  │ Simulator    │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## 🎨 FRONTEND - Web Dashboard

### Tech Stack
```json
{
  "framework": "React 19.1.1",
  "build_tool": "Vite 7.1.7",
  "language": "JavaScript (JSX)",
  "css": "Custom CSS (Glassmorphism)",
  "router": "React Router DOM 6.26.2",
  "realtime": "Socket.IO Client 4.8.1",
  "database": "Supabase JS Client 2.47.10"
}
```

### Component Architecture

#### **1. EliteUI.jsx** - Main Dashboard
**Tech:** React Hooks (useState, useEffect, useRef, useMemo)
**Functions:**
- ✅ Device tree visualization
- ✅ Real-time device status monitoring
- ✅ Script selection & execution
- ✅ Terminal command interface
- ✅ RSA key management
- ✅ File browser (C2 files)
- ✅ Auto-save/load keys from Supabase

**External Services:**
- Socket.IO for real-time device communication
- Supabase for persistent key storage
- REST API calls to Flask backend

#### **2. socketClient.js** - WebSocket Manager
**Tech:** Socket.IO Client
**Functions:**
- ✅ Establish WebSocket connection to backend
- ✅ Auto-reconnection with exponential backoff
- ✅ Event handlers for:
  - `connect` / `disconnect`
  - `server_ack` - Server acknowledgments
  - `script_output` - Command execution results
- ✅ Demo mode: auto-start device on connect

#### **3. supabase.js** - Database Client
**Tech:** @supabase/supabase-js
**Functions:**
- ✅ Create Supabase client instance
- ✅ Environment variable configuration
- ✅ Persistent session disabled (stateless)

**Operations:**
```javascript
// Save keys
supabase.from('device_keys').upsert({ user_id, device_token, public_key_pem, private_key_pem })

// Load keys
supabase.from('device_keys').select('*').eq('user_id', userId).eq('device_token', token)
```

### Build & Deployment

**Development:**
```bash
npm run dev     # Vite dev server with HMR
```

**Production:**
```bash
npm run build   # Vite optimized build
# Output: dist/ folder with:
#   - index.html
#   - assets/index-[hash].css (~20KB → 4KB gzipped)
#   - assets/index-[hash].js (~413KB → 121KB gzipped)
```

**Deploy Targets:**
- Vercel (Recommended) - SPA with vercel.json routing
- Netlify
- Static hosting (Apache/Nginx)

---

## 🔧 BACKEND - Python Flask Server

### Tech Stack
```python
{
  "framework": "Flask 3.x",
  "cors": "Flask-CORS",
  "websocket": "Flask-SocketIO + python-socketio",
  "crypto": "cryptography (RSA OAEP SHA-256, AES-GCM)",
  "web_server": "eventlet (async)",
  "production_server": "gunicorn + eventlet workers"
}
```

### Core Modules

#### **1. server.py** - Main API Server
**Lines:** 884
**Functions:**

##### REST Endpoints
```python
# Status & Info
GET  /status                     # Server health check
GET  /whoami                     # Server info
GET  /py_simple                  # HTML control panel

# Device Management
GET  /py_simple/devices          # List all connected devices
POST /device/start               # Start a device client (demo mode)
POST /py_simple/device/run       # Execute command on device via REST fallback

# RSA Key Management
POST /py_simple/keys/rsa         # Generate RSA keypair (2048-bit)
POST /py_simple/keys/unwrap      # Decrypt wrapped AES key with RSA private key
GET  /keys/last-request          # Debug: view last key request

# Encryption/Decryption
POST /encrypt                    # Trigger encryption via Socket.IO
POST /py_simple/decrypt          # Trigger decryption via Socket.IO or REST

# Scripts Management
GET  /py_simple/scripts          # List available scripts
POST /py_simple/scripts          # Add new script
PUT  /py_simple/scripts/{id}     # Update script
DELETE /py_simple/scripts/{id}   # Delete script

# C2 File Server
GET  /py_simple/c2               # List root C2 files
GET  /py_simple/c2/list?path=x   # List files in subdirectory
GET  /py_simple/c2/download?path=x # Download file
# Optional: X-C2-TOKEN header for access control

# CAPE Malware Analysis Integration
POST /py_simple/cape/report      # Submit malware analysis report
GET  /py_simple/behavior/*       # Serve behavior data
```

##### Cryptography Functions
```python
# RSA Key Generation (2048-bit)
rsa.generate_private_key(public_exponent=65537, key_size=2048)

# Key Serialization (PEM format)
private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# AES Key Unwrapping (RSA-OAEP-SHA256)
private_key.decrypt(
    wrapped_key,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    )
)
```

#### **2. socket_core.py** - Socket.IO Event Handlers
**Tech:** Flask-SocketIO
**Functions:**

```python
@socketio.on('connect')
def handle_connect():
    # Auto-generate RSA keypair for new device
    # Register device in DEVICES registry
    # Store SID (session ID) for targeting

@socketio.on('authenticate')
def handle_authenticate(data):
    # Validate device token
    # Store device metadata (hostname, IP, OS)
    # Mark device as authenticated

@socketio.on('device_hello')
def handle_device_hello(data):
    # Device registration
    # Store public key if provided
    # Broadcast device status to all clients

@socketio.on('disconnect')
def handle_disconnect():
    # Mark device offline
    # Cleanup session data
    # Broadcast status update

# Site → Device Commands
@socketio.on('site_decrypt')
def handle_site_decrypt(data):
    # Emit decrypt command to target device
    emit('decrypt', room=device_sid)

@socketio.on('site_run')
def handle_site_run(data):
    # Execute command on target device
    emit('run_script', {'command': cmd}, room=device_sid)

@socketio.on('site_keys')
def handle_site_keys(data):
    # Send RSA keys to device

# Device → Site Responses
@socketio.on('script_output')
def handle_script_output(data):
    # Receive command execution results
    # Store in device registry
    # Broadcast to all connected site clients
    emit('script_output', data, broadcast=True)
```

**In-Memory Data Structures:**
```python
DEVICES = {
    'token-abc123': {
        'sid': 'socket_session_id',
        'connected': True,
        'hostname': 'VICTIM-PC',
        'ip': '192.168.1.100',
        'public_key_pem': '-----BEGIN PUBLIC KEY-----...',
        'private_key_pem': '-----BEGIN PRIVATE KEY-----...',
        'last_output': {'stdout': '...', 'stderr': '...', 'returncode': 0}
    }
}

SCRIPTS = {
    'scriptA': {
        'label': 'Script A',
        'command': 'python device_client.py'
    }
}
```

#### **3. safe_ransomware_simulator.py** - Crypto Engine
**Tech:** Cryptography library (AES-GCM)
**Functions:**

```python
class SafeRansomwareSimulator:
    # AES-GCM 256-bit encryption
    def simulate_encryption(destructive=False):
        # Recursively encrypt files in sandbox
        # Non-destructive: creates .encrypted alongside originals
        # Destructive: moves originals to backup folder
        # Returns: list of encrypted file paths
    
    def simulate_decryption():
        # Decrypt all .encrypted files
        # Restore original files
        # Returns: list of decrypted file paths
    
    def set_key_from_base64(key_b64):
        # Load AES key from base64 (for unwrap flow)
        # Used after RSA unwrapping
    
    def get_key():
        # Export AES key as base64
        # For key wrapping with RSA public key
```

**Encryption Details:**
- Algorithm: AES-GCM (Galois/Counter Mode)
- Key Size: 256-bit
- Nonce: 96-bit (12 bytes) random
- Format: `[12-byte nonce][ciphertext]`

#### **4. behavior_simulator.py** - CAPE Integration
**Tech:** JSON data structures
**Functions:**
- ✅ Generate malware behavior logs (API calls, file operations)
- ✅ Simulate process tree
- ✅ Create network connection logs
- ✅ Mimic registry modifications

---

## 🖥️ DEVICE CLIENTS - Victim Machines

### 1. Python Device Client (`device_client.py`)

**Tech Stack:**
```python
{
  "language": "Python 3.x",
  "websocket": "python-socketio[client]",
  "http": "requests",
  "crypto": "cryptography (RSA, AES-GCM)",
  "system": "subprocess (Windows commands)"
}
```

**Functions:**

```python
# Socket.IO Event Handlers
@sio.on('connect')
def on_connect():
    # Authenticate with backend
    # Send device token

@sio.on('encrypt')
def on_encrypt(data):
    # 1. Run ransomware simulator encryption
    # 2. Get AES key from simulator
    # 3. Wrap AES key with site's RSA public key
    # 4. Save wrapped key to victim_aes.key
    # 5. Drop ransom note

@sio.on('decrypt')
def on_decrypt(data):
    # 1. Read wrapped AES key blob
    # 2. Send to backend /keys/unwrap endpoint
    # 3. Receive unwrapped AES key
    # 4. Load key into simulator
    # 5. Run decryption

@sio.on('run_script')
def on_run_script(data):
    # Execute Windows command via subprocess
    # Capture stdout, stderr, return code
    # Emit script_output back to backend
```

**Key Wrapping Flow (RSA-OAEP):**
```python
# Encrypt AES key with site's public key
public_key = serialization.load_pem_public_key(site_public_pem)
wrapped = public_key.encrypt(
    aes_key_bytes,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    )
)
```

### 2. Go Socket Client (`socket/main.go`)

**Tech Stack:**
```go
{
  "language": "Go 1.x",
  "websocket": "gorilla/websocket",
  "http": "net/http",
  "json": "encoding/json"
}
```

**Functions:**
```go
// Device Registration
func registerDevice(base, hostname) -> (device_token, ws_url)

// WebSocket Connection
func connectWS(wsURL, token) -> websocket.Conn

// Message Handlers
func handleEncrypt(data)   // Trigger encryption
func handleDecrypt(data)   // Trigger decryption
func handleRunScript(data) // Execute commands

// Command Execution
func executeCommand(cmd) -> (stdout, stderr, exitCode)
```

**Purpose:** Lightweight alternative device client in Go for cross-platform compatibility

---

## 💾 DATABASE - Supabase (PostgreSQL)

### Tech Stack
```yaml
Database: PostgreSQL (via Supabase)
Client Libraries:
  - JavaScript: @supabase/supabase-js
  - Authentication: None (anon key with RLS)
  - Storage: Tables (not buckets)
```

### Schema

#### **Table: `device_keys`**
```sql
CREATE TABLE public.device_keys (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id TEXT NOT NULL,                    -- Frontend user ID (UUID/random)
  device_token TEXT NOT NULL,               -- Device identifier
  public_key_pem TEXT,                      -- RSA public key (PEM)
  private_key_pem TEXT,                     -- RSA private key (PEM)
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  UNIQUE (user_id, device_token)            -- Composite unique constraint
);

-- Indexes
CREATE UNIQUE INDEX device_keys_user_device_unique 
  ON public.device_keys (user_id, device_token);

-- Row Level Security
ALTER TABLE public.device_keys ENABLE ROW LEVEL SECURITY;

-- Policy (Option A - Demo/Open)
CREATE POLICY "open_all_operations"
  ON device_keys
  FOR ALL
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);
```

### Data Flow

```
User Actions (EliteUI) → Supabase Operations

1. Select Device
   └─> SELECT * FROM device_keys 
       WHERE user_id = ? AND device_token = ?
       → Auto-load keys into UI

2. Click "Decrypt"
   └─> Decrypt operation runs
   └─> UPSERT INTO device_keys 
       (user_id, device_token, private_key_pem)
       → Auto-save private key

3. Generate Keys (rare - usually auto on socket)
   └─> UPSERT INTO device_keys 
       (user_id, device_token, public_key_pem, private_key_pem)
       → Save both keys
```

---

## 🔐 CRYPTOGRAPHY STACK

### Flow A: Attacker = Website, Victim = VM

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Device Registration                                │
├─────────────────────────────────────────────────────────────┤
│ Device connects → Backend auto-generates RSA keypair        │
│ Public key stored in DEVICES[token]['public_key_pem']       │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Encryption (Device/Victim)                         │
├─────────────────────────────────────────────────────────────┤
│ 1. Generate random AES-256 key                              │
│ 2. Encrypt victim files with AES-GCM                        │
│ 3. Get site's RSA public key from backend                   │
│ 4. Wrap AES key with RSA public key (OAEP-SHA256)          │
│ 5. Save wrapped key blob to victim_aes.key                  │
│ 6. Drop ransom note                                         │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Decryption (Site/Attacker)                         │
├─────────────────────────────────────────────────────────────┤
│ 1. Site sends decrypt command via Socket.IO                 │
│ 2. Device reads victim_aes.key (wrapped blob)               │
│ 3. POST to /py_simple/keys/unwrap with wrapped_key_b64      │
│ 4. Backend unwraps with RSA private key → AES key           │
│ 5. Device loads AES key into simulator                      │
│ 6. Decrypt all .encrypted files                             │
└─────────────────────────────────────────────────────────────┘
```

### Algorithms Used

| Layer | Algorithm | Key Size | Purpose |
|-------|-----------|----------|---------|
| **Transport** | TLS 1.3 | 2048-bit RSA | HTTPS/WSS encryption |
| **Asymmetric** | RSA-OAEP | 2048-bit | Key wrapping/unwrapping |
| **Hash** | SHA-256 | 256-bit | OAEP mask generation |
| **Symmetric** | AES-GCM | 256-bit | File encryption |
| **Nonce** | Random | 96-bit | GCM initialization |

---

## 🌐 DEPLOYMENT ARCHITECTURE

### Production Stack

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (site/frontend)                                │
│ ├─ Platform: Vercel                                     │
│ ├─ Build: Vite (npm run build)                          │
│ ├─ Output: Static SPA in dist/                          │
│ └─ Config: vercel.json (SPA routing)                    │
└─────────────────────────────────────────────────────────┘
         │ HTTPS + WebSocket Upgrade
         ↓
┌─────────────────────────────────────────────────────────┐
│ Backend (py_simple)                                     │
│ ├─ Platform: Render.com / AWS / DigitalOcean           │
│ ├─ Server: Gunicorn + Eventlet workers                 │
│ ├─ Command: gunicorn -k eventlet -w 1 -b 0.0.0.0:8080  │
│ │           py_simple.server:app                        │
│ └─ Environment: SANDBOX_DIR, PORT, CORS origins         │
└─────────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│ Database (Supabase)                                     │
│ ├─ Platform: Supabase Cloud                             │
│ ├─ Database: PostgreSQL 15                              │
│ ├─ Region: Auto (nearest)                               │
│ └─ Access: Direct from browser via anon key             │
└─────────────────────────────────────────────────────────┘
```

### Environment Variables

#### Frontend (`.env.local`)
```bash
VITE_API_BASE=https://your-backend.onrender.com
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Backend (Render/Server)
```bash
PORT=8080
SANDBOX_DIR=/tmp/sandbox
CORS_ORIGINS=https://your-frontend.vercel.app
C2_FILES_DIR=/path/to/c2/files
```

---

## 📦 DEPENDENCY SUMMARY

### Frontend (`site/frontend/package.json`)
```json
{
  "dependencies": {
    "@supabase/supabase-js": "^2.47.10",  // Database client
    "react": "^19.1.1",                    // UI framework
    "react-dom": "^19.1.1",                // DOM rendering
    "react-router-dom": "^6.26.2",         // Routing
    "socket.io-client": "^4.8.1"           // WebSocket client
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.0.4",      // Vite React plugin
    "eslint": "^9.36.0",                   // Code linting
    "vite": "^7.1.7"                       // Build tool
  }
}
```

### Backend (`py_simple/requirements.txt`)
```text
flask                    # Web framework
flask-cors              # Cross-origin resource sharing
flask-socketio          # WebSocket support
python-socketio         # Socket.IO protocol
websocket-client        # WebSocket client (for device)
cryptography            # RSA, AES-GCM encryption
requests                # HTTP client
eventlet                # Async I/O
gunicorn                # Production WSGI server
```

### Go Client (`socket/go.mod`)
```go
require (
    github.com/gorilla/websocket v1.5.0  // WebSocket client
)
```

---

## 🎯 FEATURE-TO-TECH MAPPING

| Feature | Frontend Tech | Backend Tech | Database | Protocol |
|---------|--------------|--------------|----------|----------|
| **Device Tree** | React State | In-memory DEVICES{} | - | REST + WebSocket |
| **Real-time Status** | Socket.IO Client | Flask-SocketIO | - | WebSocket |
| **RSA Keys** | React State | cryptography lib | Supabase | REST + DB |
| **Command Execution** | Socket.IO emit | subprocess | - | WebSocket |
| **Terminal Output** | React State | socket_output event | - | WebSocket |
| **Script Management** | Fetch API | Flask endpoints | In-memory | REST |
| **File Browser** | Fetch API | Flask + os.listdir | - | REST |
| **Encryption** | UI trigger | SafeRansomwareSimulator | - | WebSocket + AES-GCM |
| **Decryption** | UI trigger | RSA unwrap + AES-GCM | - | WebSocket + REST |
| **Key Persistence** | Supabase JS | - | PostgreSQL | REST (Supabase API) |
| **Auto-save/load** | React useEffect | - | Supabase | DB queries |

---

## 🔬 OPTIONAL INTEGRATIONS

### CAPE Sandbox (Malware Analysis)
- **Endpoint:** `POST /py_simple/cape/report`
- **Tech:** JSON data structures
- **Purpose:** Submit malware behavior analysis
- **Output:** Static behavior logs served via `/py_simple/behavior/*`

### C2 File Server
- **Tech:** Flask `send_from_directory`
- **Purpose:** Serve payloads/tools to victim machines
- **Security:** Optional X-C2-TOKEN header
- **Default Dir:** `C2_FILES_DIR` env var

---

## 📝 SUMMARY BY LANGUAGE

| Language | LOC Est. | Purpose | Key Files |
|----------|----------|---------|-----------|
| **JavaScript (JSX)** | ~800 | Frontend UI | EliteUI.jsx, socketClient.js, supabase.js |
| **Python** | ~1200 | Backend API + Device | server.py, socket_core.py, device_client.py, safe_ransomware_simulator.py |
| **Go** | ~170 | Alt device client | socket/main.go |
| **CSS** | ~1250 | UI styling | elite.css, index.css |
| **SQL** | ~50 | Database schema | Supabase SQL scripts |
| **HTML** | ~150 | Test utilities | test_supabase.html |

---

## 🎓 LEARNING RESOURCES

### Frontend Stack
- React 19: https://react.dev
- Vite: https://vite.dev
- Socket.IO Client: https://socket.io/docs/v4/client-api/
- Supabase JS: https://supabase.com/docs/reference/javascript

### Backend Stack
- Flask: https://flask.palletsprojects.com
- Flask-SocketIO: https://flask-socketio.readthedocs.io
- Python Cryptography: https://cryptography.io
- Eventlet: https://eventlet.readthedocs.io

### Database
- Supabase Docs: https://supabase.com/docs
- PostgreSQL: https://www.postgresql.org/docs/
- Row Level Security: https://supabase.com/docs/guides/auth/row-level-security

### Cryptography
- AES-GCM: https://en.wikipedia.org/wiki/Galois/Counter_Mode
- RSA-OAEP: https://en.wikipedia.org/wiki/Optimal_asymmetric_encryption_padding

---

**Last Updated:** October 18, 2025
**Project Type:** Educational C2 Lab Simulator
**License:** Use responsibly in isolated lab environments only
