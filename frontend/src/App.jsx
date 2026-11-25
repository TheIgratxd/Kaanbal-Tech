import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AuthPage from './components/auth/AuthPage';
import AppLayout from './components/layout/AppLayout';
import { AuthProvider, useAuth } from './context/AuthContext';
import { TutorSessionProvider } from './context/TutorSessionContext';
import AboutPage from './pages/AboutPage';
import DashboardPage from './pages/DashboardPage';
import DiagnosticPage from './pages/DiagnosticPage';
import ProfilePage from './pages/ProfilePage';
import TutorPage from './pages/TutorPage';

function ProtectedLayout() {
  const { accessToken } = useAuth();
  return accessToken ? <AppLayout /> : <Navigate to="/login" replace />;
}

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<AuthPage />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/diagnostico" element={<DiagnosticPage />} />
          <Route path="/tutor" element={<TutorPage />} />
          <Route path="/perfil" element={<ProfilePage />} />
          <Route path="/nosotros" element={<AboutPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <TutorSessionProvider>
        <AppRoutes />
      </TutorSessionProvider>
    </AuthProvider>
  )
}