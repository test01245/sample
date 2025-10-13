import { useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080/api'

function App() {
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const triggerDecrypt = async () => {
    try {
      setLoading(true)
  const res = await fetch(`${API_BASE}/decrypt`, { method: 'POST' })
      const data = await res.json()
      setStatus(data.status || 'Decryption request sent')
    } catch (e) {
      setStatus(`Failed to decrypt: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1>Ransomware Simulator</h1>
      <div className="panel">
        <div className="actions">
          <button onClick={triggerDecrypt} disabled={loading}>Decrypt Files</button>
        </div>
        {status && <p className="status">{status}</p>}
      </div>
    </div>
  )
}

export default App
