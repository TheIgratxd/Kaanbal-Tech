import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import AuthPage from './components/auth/AuthPage';

function DashboardPage() {
  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <nav style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <Link to="/dashboard">Inicio</Link>
        <Link to="/tutor">Tutor</Link>
        <Link to="/login">Cerrar / cambiar sesión</Link>
      </nav>
      <h1>Panel del estudiante</h1>
      <p>Vista principal después del login.</p>
    </main>
  );
}

function TutorPage() {
  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <nav style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <Link to="/dashboard">Inicio</Link>
        <Link to="/tutor">Tutor</Link>
        <Link to="/login">Cerrar / cambiar sesión</Link>
      </nav>
      <h1>Tutor socrático</h1>
      <p>Aquí irá la interacción con el backend.</p>
    </main>
  );
}

//Administra las rutas
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<AuthPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tutor" element={<TutorPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}