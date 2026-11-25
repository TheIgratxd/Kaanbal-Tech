import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

function formatDate(value) {
  if (!value) return 'No disponible'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'No disponible'
    : new Intl.DateTimeFormat('es-MX', { dateStyle: 'long' }).format(date)
}

export default function ProfilePage() {
  const { accessToken, setUser, logout } = useAuth()
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    api('/users/me', { token: accessToken })
      .then((result) => {
        if (!active) return
        setProfile(result)
        setUser(result)
      })
      .catch((requestError) => {
        if (!active) return
        setError(requestError.message)
        if (requestError.status === 401) logout()
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [accessToken, logout, retry, setUser])

  return (
    <main className="app-page">
      <header className="page-heading">
        <span className="eyebrow">Tu cuenta</span>
        <h1>Mi perfil</h1>
        <p>Consulta la información asociada a tu sesión.</p>
      </header>

      {loading && <div className="skeleton-card" aria-label="Cargando perfil" />}
      {error && (
        <section className="notice notice-error" role="alert">
          <p>{error}</p>
          <button className="app-btn" onClick={() => setRetry((value) => value + 1)}>
            Intentar de nuevo
          </button>
        </section>
      )}
      {!loading && profile && (
        <section className="app-card profile-card">
          <div className="profile-avatar" aria-hidden="true">
            {String(profile.name || 'K').trim().charAt(0).toUpperCase()}
          </div>
          <dl className="profile-fields">
            <div>
              <dt>Nombre</dt>
              <dd>{profile.name || 'No disponible'}</dd>
            </div>
            <div>
              <dt>Correo</dt>
              <dd>{profile.email || 'No disponible'}</dd>
            </div>
            <div>
              <dt>Cuenta creada</dt>
              <dd>{formatDate(profile.created_at)}</dd>
            </div>
            {profile.metadata?.academic_level && (
              <div>
                <dt>Nivel académico</dt>
                <dd>{profile.metadata.academic_level}</dd>
              </div>
            )}
          </dl>
          <p className="muted-copy">
            La edición del perfil no está disponible todavía.
          </p>
        </section>
      )}
    </main>
  )
}
