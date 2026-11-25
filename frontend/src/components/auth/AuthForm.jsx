import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function EyeIcon({ hidden }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.5 12s3.5-5.5 9.5-5.5 9.5 5.5 9.5 5.5-3.5 5.5-9.5 5.5S2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.5" />
      {hidden && <path d="M4 20 20 4" />}
    </svg>
  )
}

function AuthForm({ mode, onRegistered  }) {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
  })
  const [errors, setErrors] = useState({})
  const [showPassword, setShowPassword] = useState(false)
  const [status, setStatus] = useState('')

  const handleChange = (event) => {
    const { name, value } = event.target
    setFormData((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '' }))
    setStatus('')
  }

  const handleSubmit = async (event) => {
    event.preventDefault();

    const nextErrors = {};

    if (mode === 'register' && !formData.name.trim()) {
      nextErrors.name = 'Ingresa tu nombre';
    }

    if (!formData.email.trim()) {
      nextErrors.email = 'Ingresa tu correo';
    } else if (
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)
    ) {
      nextErrors.email = 'Ingresa un correo válido';
    }

    if (!formData.password) {
      nextErrors.password = 'Ingresa tu contraseña';
    } else if (formData.password.length < 6) {
      nextErrors.password = 'Usa al menos 6 caracteres';
    }

    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) return;

    try {
      setStatus('Procesando...');

      const endpoint =
        mode === 'login'
          ? 'login'
          : 'register';
      const apiUrl = (import.meta.env.VITE_API_URL || 'http://localhost:3000')
        .replace(/\/$/, '');

      const response = await fetch(
        `${apiUrl}/auth/${endpoint}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(
            mode === 'login'
              ? {
                  email: formData.email,
                  password: formData.password,
                }
              : formData,
          ),
        },
      );

      const result = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof result.message === 'string'
            ? result.message
            : 'No se pudo completar la solicitud.',
        );
      }

      if (mode === 'register') {
        if (result.session) {
          // Confirmación de correo desactivada: ya hay sesión
          localStorage.setItem('access_token', result.session.access_token)
          navigate('/dashboard')
        } else {
          // Hay que confirmar el correo: pasa a modo login con aviso
          onRegistered?.('Revisa tu correo para confirmar tu cuenta.')
        }
      } else {
        if (!result.session?.access_token) {
          throw new Error('No se recibió una sesión válida')
        }

        localStorage.setItem('access_token', result.session.access_token)
        navigate('/dashboard')
      }

      if (mode === 'register') {
        setStatus(
          result.session
            ? '¡Cuenta creada correctamente!'
            : 'Revisa tu correo para confirmar tu cuenta.',
        );
      } else {
        if (!result.session?.access_token) {
          throw new Error('No se recibió una sesión válida');
        }

        // Aquí puedes guardar la sesión de forma segura
        setStatus('¡Bienvenido de nuevo!');
      }

    } catch (error) {
      setStatus(error.message);
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      {mode === 'register' && (
        <div className="auth-field">
          <label htmlFor="name">Nombre</label>
          <input
            id="name"
            name="name"
            type="text"
            autoComplete="name"
            placeholder="Tu nombre"
            value={formData.name}
            onChange={handleChange}
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? 'name-error' : undefined}
          />
          {errors.name && (
            <span className="field-error" id="name-error">{errors.name}</span>
          )}
        </div>
      )}

      <div className="auth-field">
        <label htmlFor="email">Correo electrónico</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="usuario@ejemplo.com"
          value={formData.email}
          onChange={handleChange}
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? 'email-error' : undefined}
        />
        {errors.email && (
          <span className="field-error" id="email-error">{errors.email}</span>
        )}
      </div>

      <div className="auth-field">
        <label htmlFor="password">Contraseña</label>
        <div className="password-field">
          <input
            id="password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            placeholder="••••••••"
            value={formData.password}
            onChange={handleChange}
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'password-error' : undefined}
          />
          <button
            type="button"
            className="password-toggle"
            aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            onClick={() => setShowPassword((visible) => !visible)}
          >
            <EyeIcon hidden={showPassword} />
          </button>
        </div>
        {errors.password && (
          <span className="field-error" id="password-error">{errors.password}</span>
        )}
      </div>

      {mode === 'login' && (
        <a className="forgot-link" href="#recuperar">
          ¿Olvidaste tu contraseña?
        </a>
      )}

      <button className="auth-submit" type="submit">
        {mode === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}
      </button>

      {status && <p className="auth-status" role="status">{status}</p>}
    </form>
  )
}

export default AuthForm
