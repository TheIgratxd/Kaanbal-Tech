import React, { useState } from 'react';
import { DiagnosticForm } from '../components/DiagnosticForm';

const apiUrl =
  (import.meta as unknown as { env?: { VITE_API_URL?: string } }).env
    ?.VITE_API_URL ?? 'http://localhost:3000';

export const DiagnosticPage: React.FC = () => {
  const accessToken = localStorage.getItem('access_token') ?? '';
  const [educationalLevel, setEducationalLevel] = useState<string>('SECUNDARIA');
  const [grade, setGrade] = useState<number>(1);
  const [started, setStarted] = useState<boolean>(false);

  const handleLevelChange = (newLevel: string) => {
    setEducationalLevel(newLevel);
    setStarted(false);
  };

  const handleGradeChange = (newGrade: number) => {
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
    <div>
      <h2>Examen diagnóstico</h2>

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
    </div>
  );
};