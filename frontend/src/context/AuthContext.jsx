import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const AuthContext = createContext(null)

function readStoredToken() {
  try {
    return localStorage.getItem('access_token')
  } catch (error) {
    console.error('No se pudo leer la sesión guardada.', error)
    return null
  }
}

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(readStoredToken)
  const [user, setUser] = useState(null)

  const saveSession = useCallback((session, sessionUser = null) => {
    if (!session?.access_token) {
      throw new Error('La respuesta de autenticación no contiene una sesión.')
    }

    try {
      localStorage.setItem('access_token', session.access_token)
    } catch (error) {
      throw new Error('No se pudo guardar la sesión en este navegador.', {
        cause: error,
      })
    }

    setAccessToken(session.access_token)
    setUser(sessionUser)
  }, [])

  const logout = useCallback(() => {
    try {
      localStorage.removeItem('access_token')
    } catch (error) {
      console.error('No se pudo borrar la sesión guardada.', error)
    }
    setAccessToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    window.addEventListener('kaanbal:unauthorized', logout)
    return () => window.removeEventListener('kaanbal:unauthorized', logout)
  }, [logout])

  const value = useMemo(
    () => ({ accessToken, user, setUser, saveSession, logout }),
    [accessToken, user, saveSession, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider.')
  return context
}
