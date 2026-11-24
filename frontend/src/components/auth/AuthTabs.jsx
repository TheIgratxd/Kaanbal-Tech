function AuthTabs({ mode, onChange }) {
  return (
    <div className="auth-tabs" role="tablist" aria-label="Opciones de acceso">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'login'}
        className={mode === 'login' ? 'auth-tab active' : 'auth-tab'}
        onClick={() => onChange('login')}
      >
        Iniciar sesión
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'register'}
        className={mode === 'register' ? 'auth-tab active' : 'auth-tab'}
        onClick={() => onChange('register')}
      >
        Registrarse
      </button>
    </div>
  )
}

export default AuthTabs
