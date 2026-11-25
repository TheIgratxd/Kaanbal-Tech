import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { tutorApi } from '../api'
import { useAuth } from './AuthContext'

const TutorSessionContext = createContext(null)
const STORAGE_KEY = 'kaanbal:tutor-session:v1'

function loadSession() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const saved = JSON.parse(raw)
    if (
      typeof saved?.message !== 'string' ||
      !Array.isArray(saved.conversation) ||
      !saved.pedagogical_state ||
      typeof saved.pedagogical_state !== 'object'
    ) {
      sessionStorage.removeItem(STORAGE_KEY)
      return null
    }
    return saved
  } catch (error) {
    console.error('No se pudo restaurar la sesión del tutor.', error)
    return null
  }
}

export function TutorSessionProvider({ children }) {
  const { accessToken } = useAuth()
  const [session, setSession] = useState(loadSession)
  const [isStarting, setIsStarting] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [chatError, setChatError] = useState('')
  const sessionRef = useRef(session)
  const previousTokenRef = useRef(accessToken)
  const startPromiseRef = useRef(null)
  const sendingRef = useRef(false)

  useEffect(() => {
    sessionRef.current = session
    try {
      if (session) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
      else sessionStorage.removeItem(STORAGE_KEY)
    } catch (error) {
      console.error('No se pudo conservar la sesión del tutor en esta pestaña.', error)
    }
  }, [session])

  useEffect(() => {
    if (previousTokenRef.current !== accessToken) {
      sessionRef.current = null
      setSession(null)
      setChatError('')
    }
    previousTokenRef.current = accessToken
  }, [accessToken])

  const startSession = useCallback((forceNew = false) => {
    if (sessionRef.current && !forceNew) {
      return Promise.resolve(sessionRef.current)
    }
    if (startPromiseRef.current) return startPromiseRef.current

    setIsStarting(true)
    setSessionError('')
    const request = tutorApi('/sessions/start', { method: 'POST' })
      .then((result) => {
        if (
          typeof result?.message !== 'string' ||
          !Array.isArray(result.conversation) ||
          !result.pedagogical_state
        ) {
          throw new Error('El servicio de IA devolvió una sesión incompleta.')
        }
        const nextSession = {
          message: result.message,
          conversation: result.conversation,
          pedagogical_state: result.pedagogical_state,
        }
        sessionRef.current = nextSession
        setSession(nextSession)
        return nextSession
      })
      .catch((error) => {
        setSessionError(error.message)
        throw error
      })
      .finally(() => {
        startPromiseRef.current = null
        setIsStarting(false)
      })

    startPromiseRef.current = request
    return request
  }, [])

  const restartSession = useCallback(() => {
    sessionRef.current = null
    setSession(null)
    setChatError('')
    return startSession(true)
  }, [startSession])

  const sendMessage = useCallback(async (prompt) => {
    const currentSession = sessionRef.current
    if (!currentSession) throw new Error('Inicia una sesión del tutor primero.')
    if (sendingRef.current) return

    sendingRef.current = true
    setIsSending(true)
    setChatError('')

    try {
      const result = await tutorApi('/chat', {
        method: 'POST',
        timeoutMs: 120000,
        body: {
          prompt,
          conversation: currentSession.conversation,
          pedagogical_state: currentSession.pedagogical_state,
        },
      })

      if (
        typeof result?.reply !== 'string' ||
        !Array.isArray(result.conversation) ||
        !result.pedagogical_state
      ) {
        throw new Error('El servicio de IA devolvió una respuesta incompleta.')
      }

      const nextSession = {
        ...currentSession,
        conversation: result.conversation,
        pedagogical_state: result.pedagogical_state,
      }
      sessionRef.current = nextSession
      setSession(nextSession)
      return result.reply
    } catch (error) {
      setChatError(error.message)
      throw error
    } finally {
      sendingRef.current = false
      setIsSending(false)
    }
  }, [])

  const value = useMemo(
    () => ({
      session,
      isStarting,
      isSending,
      sessionError,
      chatError,
      startSession,
      restartSession,
      sendMessage,
    }),
    [
      session,
      isStarting,
      isSending,
      sessionError,
      chatError,
      startSession,
      restartSession,
      sendMessage,
    ],
  )

  return (
    <TutorSessionContext.Provider value={value}>
      {children}
    </TutorSessionContext.Provider>
  )
}

export function useTutorSession() {
  const context = useContext(TutorSessionContext)
  if (!context) {
    throw new Error('useTutorSession debe usarse dentro de TutorSessionProvider.')
  }
  return context
}
