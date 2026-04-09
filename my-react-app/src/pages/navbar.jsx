import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const location = useLocation()

  const isActive = (path) => location.pathname === path

  return (
    <nav className="nav">
      <span className="nav__logo">PlanIt</span>
      <div className="nav__links">
        <Link to="/app/home" className={isActive('/app/home') ? 'active' : ''}>🏠 Home</Link>
        <Link to="/app/destination" className={isActive('/app/destination') ? 'active' : ''}>🔍 Discover</Link>
        <Link to="/app/profile" className={isActive('/app/profile') ? 'active' : ''}>👤 Profile</Link>
      </div>
      <div className="nav__right">
        <button className="nav__icon">🔔</button>
        <button className="nav__icon">⚙️</button>
      </div>
    </nav>
  )
}