import { Link, Outlet, useLocation } from 'react-router-dom'
import './App.css'

export default function Layout() {
  const { pathname } = useLocation()
  return (
    <div className="page">
      <header className="hero">
        <div className="hero-inner">
          <h1>Developer Hub</h1>
          <p className="subtitle">Learn, simulate, and explore</p>
          <nav className="nav">
            <Link className={`nav-link ${pathname==='/'?'active':''}`} to="/">Home</Link>
            <Link className={`nav-link ${pathname.startsWith('/lab')?'active':''}`} to="/lab">Lab</Link>
          </nav>
        </div>
      </header>
      <Outlet />
      <footer className="footer">Demo build for lab use only</footer>
    </div>
  )
}
