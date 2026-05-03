import { Link, useLocation } from 'react-router-dom'
import { FaHome, FaSearchLocation, FaUser, FaBell, FaGlobeAmericas } from 'react-icons/fa'

export default function Navbar() {
  const location = useLocation()

  const isActive = (path) => location.pathname === path

  return (
    <nav className="nav">
      <Link to="/" className="nav__logo"><FaGlobeAmericas /> PlanIt</Link>
      <div className="nav__links">
        <Link to="/app/home" className={isActive('/app/home') ? 'active' : ''}> <FaHome /> Home</Link>
        <Link to="/app/destination" className={isActive('/app/destination') ? 'active' : ''}> <FaSearchLocation /> Discover</Link>
        <Link to="/app/profile" className={isActive('/app/profile') ? 'active' : ''}><FaUser /> Profile</Link>
      </div>
      <div className="nav__right">
        <button className="nav__icon"><FaBell /></button>
      </div>
    </nav>
  )
}