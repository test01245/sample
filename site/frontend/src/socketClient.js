import { io } from 'socket.io-client'

// Initializes a Socket.IO client bound to the /py_simple API base.
// Optionally asks backend to start a local device client when connecting (lab/demo).
export function initSocket({ apiBase, onStatus, onAck, onScriptOutput, startDeviceOnConnect = false }) {
  // Derive the server origin so Socket.IO connects at '/socket.io' root path
  let origin = apiBase
  try {
    const u = new URL(apiBase, window?.location?.href)
    origin = `${u.protocol}//${u.host}`
  } catch (_) { /* ignore and use as-is */ }
  const s = io(origin, { path: '/socket.io', transports: ['websocket', 'polling'] })
  const set = (v) => onStatus && onStatus(v)

  s.on('connect', async () => {
    set('connected')
    if (startDeviceOnConnect) {
      try {
        // Ask backend to spawn a device client pointing back to the same API base
        const res = await fetch(`${apiBase}/device/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ backend: apiBase, polling: true })
        })
        // eslint-disable-next-line no-unused-vars
        const _data = await res.json().catch(() => ({}))
      } catch (_) {
        // ignore errors silently in demo mode
      }
    }
  })
  s.on('disconnect', () => set('disconnected'))
  s.on('server_ack', (msg) => onAck && onAck(msg))
  s.on('script_output', (payload) => onScriptOutput && onScriptOutput(payload))
  return s
}
