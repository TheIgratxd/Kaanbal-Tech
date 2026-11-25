import { useEffect, useState } from 'react'
import { api } from '../api'

/**
 * Loads real questions from the student API and submits the completed attempt.
 */
export default function DiagnosticForm({
  accessToken,
  educationalLevel,
  grade,
}) {
  const [questions, setQuestions] = useState([])
  const [selectedOptions, setSelectedOptions] = useState({})
  const [rawAnswers, setRawAnswers] = useState({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    api(`/students/diagnostic/questions?grade=${encodeURIComponent(grade)}`, {
      token: accessToken,
    })
      .then((data) => {
        if (active) setQuestions(Array.isArray(data?.questions) ? data.questions : [])
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [accessToken, grade, retry])

  function selectOption(questionId, optionId) {
    setSelectedOptions((current) => ({ ...current, [questionId]: optionId }))
  }

  function updateRawAnswer(questionId, value) {
    setRawAnswers((current) => ({ ...current, [questionId]: value }))
  }

  async function submitAnswers(event) {
    event.preventDefault()
    setError('')

    const answers = questions.map((question) => {
      const selectedOptionId = selectedOptions[question.id]
      const rawAnswer = rawAnswers[question.id]?.trim()
      return {
        questionId: question.id,
        ...(selectedOptionId ? { selectedOptionId } : {}),
        ...(!question.options?.length && rawAnswer ? { rawAnswer } : {}),
      }
    })

    if (answers.some((answer) => !answer.selectedOptionId && !answer.rawAnswer)) {
      setError('Responde todas las preguntas antes de enviar el diagnóstico.')
      return
    }

    setSubmitting(true)
    try {
      const response = await api('/students/diagnostic', {
        method: 'POST',
        token: accessToken,
        body: {
          educationalLevel,
          grade,
          schoolYear: String(new Date().getFullYear()),
          answers,
        },
      })
      setResult(response)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <section className="app-card diagnostic-loading" aria-live="polite">
        Cargando preguntas del grado {grade}…
      </section>
    )
  }

  if (error && !questions.length) {
    return (
      <section className="notice notice-error" role="alert">
        <p>{error}</p>
        <button className="app-btn" onClick={() => setRetry((value) => value + 1)}>
          Volver a cargar
        </button>
      </section>
    )
  }

  if (!questions.length) {
    return (
      <section className="empty-panel">
        <span className="empty-mark" aria-hidden="true">?</span>
        <h2>No hay preguntas disponibles para este grado</h2>
        <p>El banco de preguntas todavía no tiene contenido activo para esta selección.</p>
      </section>
    )
  }

  return (
    <section className="diagnostic-content">
      {error && (
        <p className="notice notice-error" role="alert">{error}</p>
      )}

      {result ? (
        <section className="app-card diagnostic-result" aria-live="polite">
          <span className="eyebrow">Intento guardado</span>
          <h2>Terminaste el diagnóstico</h2>
          <p>
            Respuestas correctas: <strong>{result.correct_count}</strong> de{' '}
            <strong>{result.total_questions}</strong>.
          </p>
          <p>
            Resultado registrado: <strong>{result.percentage}%</strong>
            {result.learning_level && <> · Nivel estimado: {result.learning_level}</>}
          </p>
          <p className="muted-copy">
            Es una referencia inicial basada en este intento, no una evaluación definitiva.
          </p>
        </section>
      ) : (
        <form className="diagnostic-form" onSubmit={submitAnswers}>
          <div className="diagnostic-form-heading">
            <span className="eyebrow">{questions.length} preguntas</span>
            <p>Elige una opción o escribe tu respuesta cuando se solicite.</p>
          </div>

          {questions.map((question, index) => (
            <fieldset className="question-card" key={question.id}>
              <legend>
                <span className="question-number">{String(index + 1).padStart(2, '0')}</span>
                <span>{question.question_text}</span>
              </legend>
              {question.options?.length ? (
                <div className="answer-options">
                  {question.options.map((option) => (
                    <label className="answer-option" key={option.id}>
                      <input
                        type="radio"
                        name={`question-${question.id}`}
                        value={option.id}
                        checked={selectedOptions[question.id] === option.id}
                        onChange={() => selectOption(question.id, option.id)}
                      />
                      <span>{option.option_text}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <label className="form-control">
                  <span className="visually-hidden">Tu respuesta</span>
                  <input
                    type="text"
                    value={rawAnswers[question.id] ?? ''}
                    onChange={(event) => updateRawAnswer(question.id, event.target.value)}
                    placeholder="Escribe tu respuesta"
                  />
                </label>
              )}
            </fieldset>
          ))}

          <div className="diagnostic-submit-row">
            <p>Al enviar, tus respuestas se guardarán en tu perfil.</p>
            <button className="app-btn app-btn-lg" type="submit" disabled={submitting}>
              {submitting ? 'Guardando…' : 'Enviar diagnóstico'}
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
