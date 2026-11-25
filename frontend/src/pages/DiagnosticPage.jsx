import { useState } from 'react'
import DiagnosticForm from '../components/DiagnosticForm'
import { useAuth } from '../context/AuthContext'

export default function DiagnosticPage() {
  const { accessToken } = useAuth()
  const [educationalLevel, setEducationalLevel] = useState('SECUNDARIA')
  const [grade, setGrade] = useState(1)

  return (
    <main className="app-page">
      <header className="page-heading">
        <span className="eyebrow">Punto de partida</span>
        <h1>Diagnóstico de matemáticas</h1>
        <p>
          Responde las preguntas para obtener un resumen de este intento. No hay
          problema si alguna respuesta no te sale.
        </p>
      </header>

      <section className="app-card diagnostic-settings">
        <label className="form-control">
          <span>Nivel educativo</span>
          <select
            value={educationalLevel}
            onChange={(event) => setEducationalLevel(event.target.value)}
          >
            <option value="SECUNDARIA">Secundaria</option>
            <option value="PREPARATORIA">Preparatoria</option>
            <option value="UNIVERSIDAD">Universidad</option>
          </select>
        </label>
        <label className="form-control">
          <span>Grado</span>
          <select
            value={grade}
            onChange={(event) => setGrade(Number(event.target.value))}
          >
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
      </section>

      <DiagnosticForm
        key={`${educationalLevel}-${grade}`}
        accessToken={accessToken}
        educationalLevel={educationalLevel}
        grade={grade}
      />
    </main>
  )
}
