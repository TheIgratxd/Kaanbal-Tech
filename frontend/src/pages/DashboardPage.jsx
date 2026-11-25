import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Buenos días'
  if (h < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { accessToken, setUser, logout } = useAuth()
  const [profile, setProfile] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dashboardError, setDashboardError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    setDashboardError('')

    Promise.allSettled([
      api('/users/me', { token: accessToken }),
      api('/students/dashboard', { token: accessToken }),
    ]).then(([profileResult, dashboardResult]) => {
      if (!active) return

      if (profileResult.status === 'rejected') {
        setError(profileResult.reason.message)
        if (profileResult.reason.status === 401) logout()
        return
      }

      setProfile(profileResult.value)
      setUser(profileResult.value)

      if (dashboardResult.status === 'fulfilled') {
        setDashboard(dashboardResult.value)
      } else {
        setDashboardError(dashboardResult.reason.message)
        if (dashboardResult.reason.status === 401) logout()
      }
    }).finally(() => {
      if (active) setLoading(false)
    })

    return () => {
      active = false
    }
  }, [accessToken, logout, reloadKey, setUser])

  if (loading) {
    return (
      <main className="app-page" aria-live="polite">
        <div className="page-heading">
          <span className="eyebrow">Tu espacio de aprendizaje</span>
          <h1>Preparando tu panel...</h1>
        </div>
        <div className="skeleton-card" />
      </main>
    )
  }

  if (error) {
    return (
      <main className="app-page">
        <section className="notice notice-error" role="alert">
          <h1>No pudimos cargar tu perfil</h1>
          <p>{error}</p>
          <button className="app-btn" onClick={() => setReloadKey((key) => key + 1)}>
            Intentar de nuevo
          </button>
        </section>
      </main>
    )
  }

  const firstName = String(profile?.name || profile?.email || 'estudiante').split(' ')[0]
  const diagnostic = dashboard?.diagnostic
  const attempt = diagnostic?.latest_attempt
  const skills = diagnostic?.skills ?? []
  const level =
    profile?.metadata?.academic_level ??
    dashboard?.student?.grade ??
    'Aún no registrado'
  const hasCompletedDiagnostic = diagnostic?.completed === true

  return (
    <main className="app-page">
      <header className="page-heading">
        <span className="eyebrow">Tu espacio de aprendizaje</span>
        <h1>{greeting()}, {firstName}</h1>
        <p>Avanza a tu ritmo: primero entendemos lo que sabes y después seguimos aprendiendo.</p>
      </header>

      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <span className="dashboard-hero-mark" aria-hidden="true">K</span>
          <div>
            <p className="app-hero-kicker">Aprender paso a paso</p>
            <h2>Tu curiosidad tiene un lugar aquí.</h2>
            <p className="app-hero-text">
              El tutor te acompaña con preguntas y pistas, sin resolver por ti.
            </p>
          </div>
        </div>
        <div className="dashboard-hero-actions">
          <button className="app-btn app-btn-lg" onClick={() => navigate('/tutor')}>
            Ir al tutor <span aria-hidden="true">→</span>
          </button>
          {!hasCompletedDiagnostic && (
            <button
              className="app-btn app-btn-ghost"
              onClick={() => navigate('/diagnostico')}
            >
              Conocer mi nivel
            </button>
          )}
        </div>
      </section>

      {dashboardError && (
        <section className="notice notice-warning" role="status">
          <strong>Tu resumen no está disponible por ahora.</strong>
          <span>{dashboardError}</span>
          <button
            className="text-button"
            onClick={() => setReloadKey((key) => key + 1)}
          >
            Volver a cargar
          </button>
        </section>
      )}

      <section className="app-grid dashboard-facts" aria-label="Resumen">
        <article className="app-card fact-card">
          <span className="fact-icon" aria-hidden="true">01</span>
          <p className="app-card-label">Nivel académico</p>
          <p className="app-card-value">{level}</p>
        </article>
        <article className="app-card fact-card">
          <span className="fact-icon" aria-hidden="true">02</span>
          <p className="app-card-label">Diagnóstico</p>
          <p className="app-card-value">
            {diagnostic
              ? hasCompletedDiagnostic ? 'Completado' : 'Pendiente'
              : 'Sin información'}
          </p>
        </article>
        <article className="app-card fact-card">
          <span className="fact-icon" aria-hidden="true">03</span>
          <p className="app-card-label">Último resultado</p>
          <p className="app-card-value">
            {attempt
              ? `${attempt.correct_count} de ${attempt.total_questions} correctas`
              : 'Aún no hay intentos'}
          </p>
        </article>
      </section>

      <section className="dashboard-sections">
        <article className="app-card learning-card">
          <div className="section-title-row">
            <div>
              <span className="eyebrow">Datos reales de tus actividades</span>
              <h2>Tu diagnóstico</h2>
            </div>
            {attempt?.percentage !== undefined && (
              <span className="result-score">{Number(attempt.percentage).toFixed(0)}%</span>
            )}
          </div>
          {attempt ? (
            <>
              <p>
                Registraste {diagnostic.total_answers} respuestas. En tu intento más
                reciente, respondiste correctamente {attempt.correct_count} de{' '}
                {attempt.total_questions}.
              </p>
              <button
                className="app-btn app-btn-ghost"
                onClick={() => navigate('/diagnostico')}
              >
                Volver a practicar el diagnóstico
              </button>
            </>
          ) : (
            <div className="empty-state">
              <p>
                Aún no hay resultados guardados. Cuando completes el diagnóstico,
                aquí aparecerá tu resumen real.
              </p>
              <button className="app-btn" onClick={() => navigate('/diagnostico')}>
                Comenzar diagnóstico
              </button>
            </div>
          )}
        </article>

        <article className="app-card learning-card">
          <div className="section-title-row">
            <div>
              <span className="eyebrow">Información registrada</span>
              <h2>Habilidades</h2>
            </div>
          </div>
          {skills.length ? (
            <ul className="skill-list">
              {skills.map((skill) => {
                const score = Number(skill.mastery_score)
                const hasScore = Number.isFinite(score)
                const percent = hasScore
                  ? Math.max(0, Math.min(100, Math.round(score * 100)))
                  : 0
                return (
                  <li className="skill-item" key={skill.id}>
                    <div className="skill-heading">
                      <strong>
                        {skill.skill_id === 1 ? 'Habilidad general' : `Habilidad ${skill.skill_id}`}
                      </strong>
                      <span>{hasScore ? `${percent}%` : 'Sin estimación'}</span>
                    </div>
                    {hasScore && (
                      <div
                        className="skill-track"
                        role="progressbar"
                        aria-label={`Dominio estimado de habilidad ${skill.skill_id}`}
                        aria-valuenow={percent}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <span style={{ width: `${percent}%` }} />
                      </div>
                    )}
                    {Number.isFinite(Number(skill.confidence)) && (
                      <small>
                        Confianza de la estimación: {Math.round(Number(skill.confidence) * 100)}%
                      </small>
                    )}
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="muted-copy">
              No hay estimaciones de habilidades guardadas todavía. Se mostrarán
              cuando el servicio tenga datos disponibles.
            </p>
          )}
        </article>
      </section>

      <section className="dashboard-note">
        <span aria-hidden="true">✦</span>
        <p>Las estimaciones de aprendizaje son orientativas y pueden cambiar con nuevas evidencias.</p>
      </section>
    </main>
  )
}