import { useEffect, useMemo, useRef, useState } from 'react'
import { useTutorSession } from '../context/TutorSessionContext'

const DIMENSIONS = [
  { key: 'procedural', label: 'Procedimientos' },
  { key: 'conceptual', label: 'Comprensión conceptual' },
  { key: 'relational', label: 'Conexión entre ideas' },
]

const STRATEGIES = {
  diagnostic_question: 'Explorar tu razonamiento',
  concrete_representation: 'Usar una representación concreta',
  visual_representation: 'Explorar una representación visual',
  guided_explanation: 'Seguir una explicación guiada',
  independent_practice: 'Practicar de manera independiente',
  conceptual_challenge: 'Explorar por qué funciona',
}

const HYPOTHESIS_LABELS = {
  wrong_inverse_operation: 'Operaciones inversas',
  operates_one_side_only: 'Equilibrio de ambos lados',
  sign_error: 'Manejo de signos',
  order_of_steps_error: 'Orden de los pasos',
  rule_without_reason: 'Explicar el porqué del procedimiento',
  no_justification: 'Justificar las respuestas',
  confuses_equality_meaning: 'Significado de la igualdad',
  treats_x_as_label: 'Interpretación de la variable',
}

function messageText(message) {
  if (typeof message?.content === 'string') return message.content
  if (Array.isArray(message?.content)) {
    return message.content
      .map((part) => (typeof part?.text === 'string' ? part.text : ''))
      .join('')
  }
  return ''
}

function ProgressSummary({ state }) {
  const hypotheses = Array.isArray(state?.hypotheses)
    ? state.hypotheses.filter((item) => item.status === 'active')
    : []
  const strategy = STRATEGIES[state?.teaching_strategy]

  return (
    <aside className="tutor-side-card">
      <span className="eyebrow">Acompañamiento adaptativo</span>
      <h2>Lo que vamos observando</h2>
      <p className="muted-copy">
        Son estimaciones provisionales que pueden cambiar con nuevas respuestas.
      </p>

      <div className="estimate-list">
        {DIMENSIONS.map(({ key, label }) => {
          const estimate = state?.[key]
          const confidence = Number(estimate?.confidence ?? 0)
          const score = Number(estimate?.score)
          const hasEvidence = Number.isFinite(confidence) && confidence > 0
          const percent = Number.isFinite(score)
            ? Math.max(0, Math.min(100, Math.round(score * 100)))
            : 0

          return (
            <div className="estimate-item" key={key}>
              <div className="estimate-heading">
                <strong>{label}</strong>
                <span>{hasEvidence ? `${percent}% estimado` : 'Reuniendo evidencia'}</span>
              </div>
              {hasEvidence && (
                <>
                  <div
                    className="skill-track"
                    role="progressbar"
                    aria-label={`${label}, estimación`}
                    aria-valuenow={percent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <span style={{ width: `${percent}%` }} />
                  </div>
                  <small>
                    Confianza de la observación: {Math.round(confidence * 100)}%
                  </small>
                </>
              )}
            </div>
          )
        })}
      </div>

      {strategy && (
        <div className="strategy-note">
          <span>Enfoque actual</span>
          <strong>{strategy}</strong>
        </div>
      )}

      {hypotheses.length > 0 && (
        <div className="hypothesis-note">
          <span>Aspectos por explorar</span>
          <ul>
            {hypotheses.map((item, index) => (
              <li key={`${item.label}-${index}`}>
                {HYPOTHESIS_LABELS[item.label] || 'Una idea que seguiremos explorando'}
              </li>
            ))}
          </ul>
          <small>No son conclusiones definitivas.</small>
        </div>
      )}
    </aside>
  )
}

export default function TutorPage() {
  const {
    session,
    isStarting,
    isSending,
    sessionError,
    chatError,
    startSession,
    restartSession,
    sendMessage,
  } = useTutorSession()
  const [draft, setDraft] = useState('')
  const [localError, setLocalError] = useState('')
  const transcriptEndRef = useRef(null)
  const formRef = useRef(null)

  useEffect(() => {
    if (!session) startSession().catch(() => {})
  }, [session, startSession])

  const messages = useMemo(() => {
    const transcript = []
    if (session?.message) {
      transcript.push({
        role: 'assistant',
        text: session.message,
        id: 'welcome',
      })
    }
    for (const [index, message] of (session?.conversation ?? []).entries()) {
      const text = messageText(message)
      if (text) {
        transcript.push({
          role: message.role === 'user' ? 'user' : 'assistant',
          text,
          id: `${message.role}-${index}`,
        })
      }
    }
    return transcript
  }, [session])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isSending])

  async function submitMessage(event) {
    event.preventDefault()
    const prompt = draft.trim()
    if (!prompt || isSending || !session) return

    setLocalError('')
    try {
      await sendMessage(prompt)
      setDraft('')
    } catch (error) {
      setLocalError(error.message)
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <main className="app-page tutor-page">
      <header className="page-heading tutor-page-heading">
        <span className="eyebrow">Tu espacio de práctica</span>
        <h1>Tutor Kaanbal</h1>
        <p>Piensa en voz alta. El tutor te ayudará a encontrar el siguiente paso.</p>
      </header>

      {isStarting && !session && (
        <section className="app-card tutor-loading" aria-live="polite">
          Preparando tu sesión de aprendizaje…
        </section>
      )}

      {sessionError && !session && (
        <section className="notice notice-error" role="alert">
          <div>
            <strong>No pudimos iniciar el tutor.</strong>
            <p>{sessionError}</p>
          </div>
          <button className="app-btn" onClick={() => startSession().catch(() => {})}>
            Intentar de nuevo
          </button>
        </section>
      )}

      {session && (
        <div className="tutor-layout">
          <section className="chat-card" aria-label="Conversación con el tutor">
            <header className="chat-header">
              <div className="chat-avatar" aria-hidden="true">K</div>
              <div>
                <strong>Kaanbal</strong>
                <span>
                  Tutor de matemáticas ·{' '}
                  {session.pedagogical_state.phase === 'practice' ? 'Práctica' : 'Diagnóstico'}
                </span>
              </div>
              <button
                className="text-button chat-reset"
                type="button"
                disabled={isSending || isStarting}
                onClick={() => restartSession().catch(() => {})}
              >
                Nueva sesión
              </button>
            </header>

            <div className="chat-transcript" aria-live="polite">
              {messages.map((message) => (
                <article
                  className={`chat-message chat-message-${message.role}`}
                  key={message.id}
                >
                  <span className="chat-message-label">
                    {message.role === 'user' ? 'Tú' : 'Tutor Kaanbal'}
                  </span>
                  <p>{message.text}</p>
                </article>
              ))}
              {isSending && (
                <div className="chat-message chat-message-assistant chat-thinking" role="status">
                  <span className="chat-message-label">Tutor Kaanbal</span>
                  <p>Estoy pensando en una pista para ti…</p>
                </div>
              )}
              <div ref={transcriptEndRef} />
            </div>

            {(localError || chatError) && (
              <div className="chat-error" role="alert">
                <span>{localError || chatError}</span>
                {draft.trim() && (
                  <button
                    className="text-button"
                    type="button"
                    disabled={isSending}
                    onClick={() => formRef.current?.requestSubmit()}
                  >
                    Reintentar
                  </button>
                )}
              </div>
            )}

            <form
              className="chat-compose"
              ref={formRef}
              onSubmit={submitMessage}
            >
              <label className="visually-hidden" htmlFor="tutor-message">
                Escribe tu respuesta
              </label>
              <textarea
                id="tutor-message"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Escribe cómo lo estás pensando…"
                maxLength={10000}
                rows={2}
                disabled={isSending}
              />
              <button
                className="app-btn chat-send"
                type="submit"
                disabled={!draft.trim() || isSending}
                aria-label={isSending ? 'Enviando respuesta' : 'Enviar respuesta'}
              >
                {isSending ? 'Enviando…' : 'Enviar'}
              </button>
              <small>Enter para enviar · Shift + Enter para escribir otra línea</small>
            </form>
          </section>

          <ProgressSummary state={session.pedagogical_state} />
        </div>
      )}
    </main>
  )
}