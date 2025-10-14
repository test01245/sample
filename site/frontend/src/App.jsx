import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'

function App() {
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [hostname, setHostname] = useState('')
  const [deviceInfo, setDeviceInfo] = useState(null)
  const [devices, setDevices] = useState([])
  const [selectedToken, setSelectedToken] = useState('')
  const [publicKey, setPublicKey] = useState('')
  const [privateKey, setPrivateKey] = useState('')
  const [adminToken, setAdminToken] = useState('')
  const [serverHost, setServerHost] = useState('')
  const socketRef = useRef(null)
  const [socketStatus, setSocketStatus] = useState('disconnected')

  useEffect(() => {
    // Load backend status for server hostname display
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/status`)
        const data = await res.json()
        if (data?.hostname) setServerHost(data.hostname)
      } catch (_) {
        // ignore
      }
    }
    fetchStatus()
  // Also load last recorded device info on first load
  refreshDeviceInfo()
  loadDevices()

    // Socket.IO connect (for sending public keys and decrypt triggers)
    try {
      const s = io(API_BASE, { path: '/socket.io', transports: ['websocket', 'polling'] })
      socketRef.current = s
      s.on('connect', () => setSocketStatus('connected'))
      s.on('disconnect', () => setSocketStatus('disconnected'))
      s.on('server_ack', (msg) => {
        if (msg?.status === 'ok') setStatus('Server acknowledged request')
      })
    } catch (_) {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const triggerDecrypt = async () => {
    try {
      setLoading(true)
      if (socketRef.current && socketStatus === 'connected') {
        socketRef.current.emit('site_decrypt', privateKey ? { private_key_pem: privateKey } : {})
        setStatus('Decrypt request sent via socket')
      } else {
        const res = await fetch(`${API_BASE}/decrypt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(privateKey ? { private_key_pem: privateKey } : {}),
        })
        const data = await res.json()
        setStatus(data.status || 'Decryption request sent')
      }
    } catch (e) {
      setStatus(`Failed to decrypt: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const requestPublicKey = async () => {
    try {
      setLoading(true)
      setStatus('')
      const res = await fetch(`${API_BASE}/keys/rsa`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hostname: hostname || null }),
      })
      const data = await res.json()
      if (res.ok) {
        setPublicKey(data.public_key_pem || '')
        setDeviceInfo(data.device || null)
        setStatus('Public key generated and device info recorded')
      } else {
        setStatus(`Public key request failed: ${data.error || res.status}`)
      }
    } catch (e) {
      setStatus(`Public key request error: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const refreshDeviceInfo = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/keys/last-request`)
      const data = await res.json()
      setDeviceInfo(Object.keys(data || {}).length ? data : null)
      setStatus('Device info refreshed')
    } catch (e) {
      setStatus(`Failed to load device info: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const loadDevices = async () => {
    try {
      const res = await fetch(`${API_BASE}/devices`)
      const data = await res.json()
      setDevices(data.devices || [])
      if ((data.devices || []).length && !selectedToken) {
        setSelectedToken(data.devices[0].token)
      }
    } catch (_) {
      // ignore
    }
  }

  const attachPublicKeyToDevice = async () => {
    if (!selectedToken || !publicKey) {
      setStatus('Select a device and generate a public key first')
      return
    }
    try {
      setLoading(true)
      if (socketRef.current && socketStatus === 'connected') {
        socketRef.current.emit('site_public_key', { token: selectedToken, public_key_pem: publicKey })
        setStatus('Public key sent via socket')
        loadDevices()
      } else {
        const res = await fetch(`${API_BASE}/devices/${selectedToken}/public-key`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ public_key_pem: publicKey }),
        })
        if (res.ok) {
          setStatus('Public key attached to device')
          loadDevices()
        } else {
          const data = await res.json()
          setStatus(`Attach failed: ${data.error || res.status}`)
        }
      }
    } catch (e) {
      setStatus(`Attach error: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const requestPrivateKey = async () => {
    try {
      setLoading(true)
      setStatus('')
      setPrivateKey('')
      const res = await fetch(`${API_BASE}/keys/rsa/private`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-ADMIN-TOKEN': adminToken || '',
        },
      })
      const data = await res.json()
      if (res.ok && data?.private_key_pem) {
        setPrivateKey(data.private_key_pem)
        setStatus('Private key generated (admin)')
      } else {
        setStatus(`Private key request failed: ${data?.message || data?.error || res.status}`)
      }
    } catch (e) {
      setStatus(`Private key request error: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setStatus('Copied to clipboard')
    } catch (e) {
      setStatus('Copy failed')
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-inner">
          <h1>Ransomware Simulator</h1>
          <p className="subtitle">Safe, reversible AES-GCM demo</p>
          {serverHost && <div className="badge">Backend Host: {serverHost}</div>}
        </div>
      </header>

      <main className="container">
        <section className="card grid">
          <div className="card-section">
            <h2>Quick Actions</h2>
            <p className="muted">Trigger a full decrypt on the backend</p>
            <div className="actions">
              <button className="btn primary" onClick={triggerDecrypt} disabled={loading}>
                {loading ? 'Working…' : 'Decrypt Files'}
              </button>
            </div>
            {status && <div className="toast">{status}</div>}
          </div>

          <div className="card-section">
            <h2>Device & Public Key</h2>
            <div className="muted" style={{marginBottom: 8}}>Socket: {socketStatus}</div>
            <div className="field">
              <label>Connected Devices</label>
              <select className="input" value={selectedToken} onChange={(e) => setSelectedToken(e.target.value)}>
                {devices.map(d => (
                  <option key={d.token} value={d.token}>
                    {d.hostname || d.token.slice(0,8)} • {d.ip || 'ip?'} • {d.connected ? 'online' : 'offline'}
                  </option>
                ))}
              </select>
              <button className="btn ghost" onClick={loadDevices} style={{marginTop: 8}}>Refresh</button>
            </div>
            <div className="field">
              <label>Device Hostname (optional)</label>
              <input
                className="input"
                type="text"
                placeholder="Enter VM hostname"
                value={hostname}
                onChange={(e) => setHostname(e.target.value)}
              />
            </div>
            <div className="actions">
              <button className="btn" onClick={requestPublicKey} disabled={loading}>Generate Public Key</button>
              <button className="btn" onClick={attachPublicKeyToDevice} disabled={loading || !selectedToken || !publicKey}>Attach to Device</button>
              <button className="btn" onClick={refreshDeviceInfo} disabled={loading}>Refresh Device Info</button>
            </div>

            {deviceInfo && (
              <div className="kv">
                <div><span className="k">Requester IP</span><span className="v">{deviceInfo.requester_ip || '—'}</span></div>
                <div><span className="k">Requester Hostname</span><span className="v">{deviceInfo.requester_hostname || '—'}</span></div>
                <div><span className="k">Timestamp</span><span className="v">{deviceInfo.timestamp ? new Date(deviceInfo.timestamp * 1000).toLocaleString() : '—'}</span></div>
              </div>
            )}

            {publicKey && (
              <div className="field">
                <label>Public Key (PEM)</label>
                <div className="code">
                  <pre>{publicKey}</pre>
                  <button className="btn ghost" onClick={() => copyToClipboard(publicKey)}>Copy</button>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="card">
          <h2>Admin: Private Key</h2>
          <p className="muted">Protected endpoint. Enter the admin token (set in backend as ADMIN_TOKEN; default for lab is "secretfr").</p>
          <div className="field">
            <label>Admin Token</label>
            <input
              className="input"
              type="password"
              placeholder="Enter admin token"
              value={adminToken}
              onChange={(e) => setAdminToken(e.target.value)}
            />
          </div>
          <div className="actions">
            <button className="btn danger" onClick={requestPrivateKey} disabled={loading || !adminToken}>
              {loading ? 'Working…' : 'Get Private Key'}
            </button>
          </div>
          {privateKey && (
            <div className="field">
              <label>Private Key (PEM)</label>
              <div className="code">
                <pre>{privateKey}</pre>
                <button className="btn ghost" onClick={() => copyToClipboard(privateKey)}>Copy</button>
              </div>
            </div>
          )}
        </section>
      </main>

      <footer className="footer">Demo build for lab use only</footer>
    </div>
  )
}

export default App
