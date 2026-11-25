import { NavLink, Outlet, useNavigate } from 'react-router-dom'

export default function AppLayout() {
  const navigate = useNavigate()

  const logout = () => {
    localStorage.removeItem('access_token')
    navigate('/login', { replace: true })
  }

  return (
    <>
      <nav style={{ display: 'flex', gap: '1rem', padding: '1rem', fontFamily: 'system-ui, sans-serif' }}>
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/diagnostico">Diagnóstico</NavLink>
        <NavLink to="/tutor">Tutor IA</NavLink>
        <NavLink to="/nosotros">Nosotros</NavLink>
        <button onClick={logout} style={{ marginLeft: 'auto' }}>
          Cerrar sesión
        </button>
      </nav>
      <Outlet />
    </>
  )
}