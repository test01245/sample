import { useEffect, useState } from 'react'

export default function C2Browser({ apiBase }) {
  const [root, setRoot] = useState(null)
  const [items, setItems] = useState([])
  const [path, setPath] = useState('')
  const [downloadUrl, setDownloadUrl] = useState('')
  const [error, setError] = useState('')

  async function fetchJSON(url) {
    const r = await fetch(url)
    const j = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(j.message || j.error || ('HTTP ' + r.status))
    return j
  }

  async function loadRoot() {
    try {
      const data = await fetchJSON(`${apiBase}/c2`)
      setRoot(data.root)
      setItems(data.files || [])
      setPath('')
      setError('')
    } catch (e) { setError(e.message) }
  }

  async function enter(sub) {
    const newPath = path ? `${path}/${sub}` : sub
    try {
      const data = await fetchJSON(`${apiBase}/c2/list?path=${encodeURIComponent(newPath)}`)
      setItems(data.files || [])
      setPath(newPath)
      setError('')
    } catch (e) { setError(e.message) }
  }

  function up() {
    if (!path) return
    const segs = path.split('/').filter(Boolean)
    segs.pop()
    const newPath = segs.join('/')
    if (!newPath) return loadRoot()
    fetchJSON(`${apiBase}/c2/list?path=${encodeURIComponent(newPath)}`)
      .then(data => { setItems(data.files || []); setPath(newPath); setError('') })
      .catch(e => setError(e.message))
  }

  function download(name) {
    const rel = path ? `${path}/${name}` : name
    const url = `${apiBase}/c2/download?path=${encodeURIComponent(rel)}`
    setDownloadUrl(url)
  }

  useEffect(() => { loadRoot() }, [apiBase])

  return (
    <div className="card">
      <div className="row" style={{justifyContent:'space-between'}}>
        <h3 style={{margin:'.25rem 0'}}>C2 Files</h3>
        <div className="row">
          <button className="btn" onClick={up} disabled={!path}>Up</button>
          <button className="btn" onClick={loadRoot}>Reload</button>
        </div>
      </div>
      <p className="muted">Root: {root || 'not configured'} {path && (<span> · Path: {path}</span>)} </p>
      {error && <div className="muted">Error: {error}</div>}
      <div style={{display:'grid', gridTemplateColumns:'1fr 140px 120px', gap:'.25rem'}}>
        <div className="label">Name</div>
        <div className="label">Size</div>
        <div className="label">Action</div>
        {(items||[]).map(item => (
          <>
            <div>{item.is_dir ? '📁 ' : '📄 '}{item.name}</div>
            <div>{item.is_dir ? '-' : (item.size || 0)}</div>
            <div>
              {item.is_dir ? (
                <button className="btn" onClick={() => enter(item.name)}>Open</button>
              ) : (
                <button className="btn" onClick={() => download(item.name)}>Download</button>
              )}
            </div>
          </>
        ))}
      </div>
      {downloadUrl && (
        <div style={{marginTop:'.5rem'}}>
          <div className="label">Direct download URL</div>
          <input className="input" value={downloadUrl} readOnly onFocus={(e)=>e.target.select()} />
        </div>
      )}
    </div>
  )
}
