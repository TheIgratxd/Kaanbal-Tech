import { useState } from 'react'
import AuthTabs from './AuthTabs'
import AuthForm from './AuthForm'
import BrandPanel from './BrandPanel'
import './auth.css'

function AuthPage() {
  const [mode, setMode] = useState('login')
  const [notice, setNotice] = useState('')

  const changeMode = (nextMode) => {
    setNotice('') // limpia el aviso al cambiar de pestaña manualmente
    setMode(nextMode)
  }

  const handleRegistered = (message) => {
    setMode('login')
    setNotice(message)
  }

  return (
    <main className="auth-page">
      <div className="auth-shell">
        <BrandPanel />

        <section className="auth-form-panel" aria-label="Acceso a Kaanbal">
          <div className="auth-card">
            <AuthTabs mode={mode} onChange={changeMode} />

            <header className="auth-header">
              <p className="auth-kicker">
                {mode === 'login' ? 'Qué bueno verte' : 'Empieza hoy'}
              </p>
              <h2>
                {mode === 'login'
                  ? 'Bienvenido de nuevo'
                  : 'Crea tu cuenta'}
              </h2>
              <p>
                {mode === 'login'
                  ? 'Ingresa tus datos para continuar'
                  : 'Completa tus datos para registrarte'}
              </p>
            </header>

            {notice && (
              <p className="auth-status" role="status">
                {notice}
              </p>
            )}

            <AuthForm
              key={mode}
              mode={mode}
              onRegistered={handleRegistered}
            />

            <p className="security-note">
              <span aria-hidden="true">●</span>
              Conexión segura
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}

export default AuthPage