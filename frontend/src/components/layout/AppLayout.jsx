import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export default function AppLayout() {
  const navigate = useNavigate()
  const { logout: signOut } = useAuth()

  const logout = () => {
    signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-shell">
      <nav className="app-nav" aria-label="Navegación principal">
        <Link className="app-brand" to="/dashboard" aria-label="Kaanbal, inicio">
          <span className="app-brand-mark" aria-hidden="true">K</span>
          <span>Kaanbal</span>
        </Link>
        <div className="app-nav-links">
          <NavLink to="/dashboard">Inicio</NavLink>
          <NavLink to="/diagnostico">Diagnóstico</NavLink>
          <NavLink to="/tutor">Tutor IA</NavLink>
          <NavLink to="/perfil">Mi perfil</NavLink>
        </div>
        <button className="app-btn app-btn-ghost app-logout" onClick={logout}>
          Cerrar sesión
        </button>
      </nav>
      <Outlet />
      <footer className="app-footer">
        <Link to="/nosotros">Kaanbal</Link>
        <span>Aprender también es preguntar.</span>
      </footer>
    </div>
  )
}