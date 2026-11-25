import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

const QUOTES = [
  'Cada pregunta que haces es un paso más cerca de entender.',
  'No se trata de saberlo todo, sino de no dejar de preguntar.',
  'Equivocarte es parte de aprender. Sigue intentando.',
  'Pequeños avances cada día valen más que un gran esfuerzo un día.',
  'Hoy es un buen día para aprender algo nuevo.',
  'Tu curiosidad es tu mejor herramienta.',
  'Lo difícil de hoy será lo fácil de mañana.',
]

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return '¡Buenos días'
  if (h < 19) return '¡Buenas tardes'
  return '¡Buenas noches'
}

function dayOfYear() {
  const now = new Date()
  return Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 86400000)
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [student, setStudent] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/users/me')
      .then(setStudent)
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <main className="app-page"><p className="app-error">{error}</p></main>
  if (!student) return <main className="app-page"><p>Cargando...</p></main>

  const firstName = String(student.name).split(' ')[0]
  const hasLevel = Boolean(student.academic_level)
  const hasDiagnostic = Boolean(student.diagnostic_done)

  const steps = [
    { title: 'Crea tu cuenta', text: '¡Ya diste el primer paso!', done: true },
    { title: 'Elige tu nivel', text: 'Cuéntanos en qué nivel académico estás.', done: hasLevel },
    { title: 'Examen diagnóstico', text: 'Descubre dónde estás parado.', done: hasDiagnostic },
    { title: 'Aprende con tu tutor', text: 'Preguntas guiadas, a tu ritmo.', done: false },
  ]
  const currentIndex = steps.findIndex((s) => !s.done)
  const completed = steps.filter((s) => s.done).length
  const percent = Math.round((completed / steps.length) * 100)

  const daysWithUs =
    Math.floor((Date.now() - new Date(student.created_at).getTime()) / 86400000) + 1

  return (
    <main className="app-page">
      {/* Banner de bienvenida */}
      <section className="app-hero">
        <div>
          <p className="app-hero-kicker">{greeting()}!</p>
          <h1>{firstName}, ¡a aprender!</h1>
          <p className="app-hero-text">
            {hasDiagnostic
              ? 'Tu tutor ya sabe dónde estás. Hoy toca seguir avanzando.'
              : 'Tu aventura de aprendizaje empieza aquí. Un paso a la vez.'}
          </p>
          <button className="app-btn app-btn-lg" onClick={() => navigate('/tutor')}>
            {hasDiagnostic ? 'Continuar con mi tutor →' : 'Empezar ahora →'}
          </button>
        </div>
        <div className="app-hero-badge" aria-hidden="true">
          <span>{daysWithUs}</span>
          <small>{daysWithUs === 1 ? 'día' : 'días'} con Kaanbal</small>
        </div>
      </section>

      {/* Estadísticas */}
      <section className="app-grid">
        <div className="app-card">
          <p className="app-card-label">Nivel académico</p>
          <p className="app-card-value">{student.academic_level ?? 'Por definir'}</p>
        </div>
        <div className="app-card">
          <p className="app-card-label">Examen diagnóstico</p>
          <p className="app-card-value">
            <span className={`app-badge ${hasDiagnostic ? 'app-badge-ok' : 'app-badge-pending'}`}>
              {hasDiagnostic ? 'Completado' : 'Pendiente'}
            </span>
          </p>
        </div>
        <div className="app-card">
          <p className="app-card-label">Tu progreso</p>
          <p className="app-card-value">{percent}%</p>
        </div>
      </section>

      {/* Ruta de aprendizaje */}
      <section className="app-card app-path">
        <div className="app-path-head">
          <h2>Tu ruta de aprendizaje</h2>
          <span className="app-path-count">{completed} de {steps.length} pasos</span>
        </div>

        <div
          className="app-progress"
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="app-progress-fill" style={{ width: `${percent}%` }} />
        </div>

        <ol className="app-steps">
          {steps.map((step, i) => {
            const state = step.done ? 'done' : i === currentIndex ? 'current' : 'locked'
            return (
              <li key={step.title} className={`app-step app-step-${state}`}>
                <span className="app-step-num">{step.done ? '✓' : i + 1}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
              </li>
            )
          })}
        </ol>
      </section>

      {/* Frase del día */}
      <section className="app-quote">
        <span aria-hidden="true">💡</span>
        <p>{QUOTES[dayOfYear() % QUOTES.length]}</p>
      </section>
    </main>
  )
}