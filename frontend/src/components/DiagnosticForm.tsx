import React, { useEffect, useState } from 'react';

interface OptionItem {
  id: string;
  question_id: string;
  option_text: string;
  order_index: number;
}

interface QuestionItem {
  id: string;
  grade: number;
  question_type: string;
  question_text: string;
  max_score: number;
  order_index: number | null;
  options: OptionItem[];
}

interface DiagnosticFormProps {
  apiBaseUrl?: string;
  accessToken: string;
  educationalLevel: string;
  grade: number;
  schoolYear?: string;
  onCompleted?: (result: Record<string, unknown>) => void;
}

export const DiagnosticForm: React.FC<DiagnosticFormProps> = ({
  apiBaseUrl = 'http://localhost:3000',
  accessToken,
  educationalLevel,
  grade,
  schoolYear,
  onCompleted,
}) => {
  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({});
  const [rawAnswers, setRawAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let active = true;

    async function loadQuestions() {
      setLoading(true);
      setError(null);
      setResult(null);
      setSelectedOptions({});
      setRawAnswers({});

      try {
        const res = await fetch(
          `${apiBaseUrl}/students/diagnostic/questions?grade=${encodeURIComponent(grade)}`,
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          },
        );

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || 'No se pudieron cargar las preguntas');
        }

        if (active) {
          const list: QuestionItem[] = Array.isArray(data.questions)
            ? data.questions
            : [];
          const randomized = [...list].sort(() => Math.random() - 0.5).slice(0, 5);
          setQuestions(randomized);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Error al cargar preguntas');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    if (grade && accessToken) {
      loadQuestions();
    }

    return () => {
      active = false;
    };
  }, [apiBaseUrl, accessToken, grade]);

  function handleSelectOption(questionId: string, optionId: string) {
    setSelectedOptions((prev) => ({
      ...prev,
      [questionId]: optionId,
    }));
  }

  function handleRawAnswerChange(questionId: string, value: string) {
    setRawAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const payloadAnswers = questions.map((q) => {
      const hasOptions = q.options && q.options.length > 0;
      return {
        questionId: q.id,
        ...(hasOptions && selectedOptions[q.id]
          ? { selectedOptionId: selectedOptions[q.id] }
          : {}),
        ...(!hasOptions || rawAnswers[q.id]?.trim()
          ? { rawAnswer: (rawAnswers[q.id] ?? '').trim() }
          : {}),
      };
    });

    const unanswered = payloadAnswers.filter(
      (item) => !item.selectedOptionId && !item.rawAnswer,
    );

    if (unanswered.length > 0) {
      setError('Responde todas las preguntas antes de enviar el diagnóstico.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${apiBaseUrl}/students/diagnostic`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          educationalLevel,
          grade,
          ...(schoolYear ? { schoolYear } : {}),
          answers: payloadAnswers,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Error al enviar el diagnóstico');
      }

      setResult(data);
      onCompleted?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al enviar respuestas');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div>Cargando preguntas para el grado {grade}...</div>;
  }

  if (error) {
    return <div role="alert">{error}</div>;
  }

  if (!questions.length) {
    return <div>No hay preguntas activas registradas para el grado {grade}.</div>;
  }

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <strong>Nivel:</strong> {educationalLevel} | <strong>Grado:</strong> {grade}
      </div>

      {questions.map((question, index) => {
        const hasOptions = question.options && question.options.length > 0;

        return (
          <fieldset key={question.id}>
            <legend>
              Pregunta {index + 1}: {question.question_text}
            </legend>

            {hasOptions ? (
              question.options.map((opt) => (
                <label key={opt.id}>
                  <input
                    type="radio"
                    name={`question-${question.id}`}
                    value={opt.id}
                    checked={selectedOptions[question.id] === opt.id}
                    onChange={() => handleSelectOption(question.id, opt.id)}
                  />
                  {opt.option_text}
                </label>
              ))
            ) : (
              <input
                type="text"
                placeholder="Escribe tu respuesta"
                value={rawAnswers[question.id] ?? ''}
                onChange={(e) => handleRawAnswerChange(question.id, e.target.value)}
              />
            )}
          </fieldset>
        );
      })}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Evaluando...' : 'Enviar diagnóstico'}
      </button>

      {result !== null && (
        <pre>{JSON.stringify(result, null, 2)}</pre>
      )}
    </form>
  );
};