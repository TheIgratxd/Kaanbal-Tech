import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AuthPage from './components/auth/AuthPage';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/DashboardPage';
import { DiagnosticForm } from './components/DiagnosticForm';

const apiUrl =
  (import.meta?.env?.VITE_API_URL) ?? 'http://localhost:3000';

function PrivateRoute({ children }) {
  return localStorage.getItem('access_token')
    ? children
    : <Navigate to="/login" replace />;
}

function TutorPage() {
  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Tutor socrático</h1>
      <p>Aquí irá la interacción con el backend.</p>
    </main>
  );
}

function DiagnosticView() {
  const accessToken = localStorage.getItem('access_token') ?? '';
  const [educationalLevel, setEducationalLevel] = useState('SECUNDARIA');
  const [grade, setGrade] = useState(1);
  const [started, setStarted] = useState(false);

  const handleLevelChange = (newLevel) => {
    setEducationalLevel(newLevel);
    setStarted(false);
  };

  const handleGradeChange = (newGrade) => {
    setGrade(newGrade);
    setStarted(false);
  };

  const handleStartExam = () => {
    if (!accessToken) {
      return;
    }
    setStarted(true);
  };

  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Examen diagnóstico</h1>

      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
        <label>
          Nivel educativo:
          <select
            value={educationalLevel}
            onChange={(e) => handleLevelChange(e.target.value)}
          >
            <option value="SECUNDARIA">Secundaria</option>
            <option value="PREPARATORIA">Preparatoria</option>
            <option value="UNIVERSIDAD">Universidad</option>
          </select>
        </label>

        <label>
          Grado de tutoría:
          <select
            value={grade}
            onChange={(e) => handleGradeChange(Number(e.target.value))}
          >
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>

        <button type="button" onClick={handleStartExam} disabled={!accessToken}>
          {started ? 'Reiniciar diagnóstico' : 'Comenzar diagnóstico'}
        </button>
      </div>

      {!accessToken && (
        <p role="alert">
          No se encontró un token de sesión. Inicia sesión antes de realizar el diagnóstico.
        </p>
      )}

      {started && accessToken && (
        <DiagnosticForm
          key={`${educationalLevel}-${grade}`}
          apiBaseUrl={apiUrl}
          accessToken={accessToken}
          educationalLevel={educationalLevel}
          grade={grade}
          onCompleted={(res) => {
            console.log('Diagnóstico guardado:', res);
          }}
        />
      )}
    </main>
  );
}

function AboutPage() {
  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Nosotros</h1>
      <p>Somos el equipo de Kaanbal Tech.</p>
    </main>
  );
}

// Administra las rutas
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<AuthPage />} />

        {/* Rutas protegidas: comparten el layout con la barra de navegación */}
        <Route
          element={
            <PrivateRoute>
              <AppLayout />
            </PrivateRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/diagnostico" element={<DiagnosticView />} />
          <Route path="/tutor" element={<TutorPage />} />
          <Route path="/tutor/diagnostico" element={<DiagnosticView />} />
          <Route path="/nosotros" element={<AboutPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}