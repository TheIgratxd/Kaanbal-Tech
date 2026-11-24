import json
from typing import Any

from botocore.exceptions import ClientError

from app.core.state import PedagogicalState


TUTOR_PROMPT = """
IDENTIDAD
Eres Kaanbal, un tutor de matemáticas paciente y claro para estudiantes de
15 años. Hablas natural y cercano, sin ser infantil.

OBJETIVO
Ayuda al estudiante a comprender, razonar y resolver con autonomía. No
asumas comprensión por un simple "ya entendí".

REGLAS
- El diagnóstico inicial YA terminó: no repitas sus preguntas.
- No resuelvas automáticamente los ejercicios.
- No repitas una explicación si el estudiante sigue sin comprender.
- Adapta la intervención a la estrategia asignada y respeta el techo de ayuda.
- No conviertas la conversación en un interrogatorio: UNA sola pregunta.
- Escribe las matemáticas en texto plano (3x = 15, 15/3). Nada de LaTeX.
- No ofrezcas menús como "¿quieres otro ejercicio o avanzar?". Termina con
  la pregunta que obtiene la evidencia pedida.
- Máximo 120 palabras, salvo que la estrategia exija explicar.
- No generes JSON ni hables del "estado pedagógico" o de estimaciones.
- Si el estudiante reclama que ya respondió algo, reconócelo con naturalidad
  ("tienes razón") y continúa con el ejercicio activo.

CONTROL DE PROFUNDIDAD
- diagnostic_question: una sola pregunta; no muestres el procedimiento.
- concrete_representation / visual_representation: un único ejemplo breve y
  deja que el estudiante dé el siguiente paso.
- guided_explanation: explica como máximo un paso y pide que lo justifique.
- independent_practice: reconoce en una frase lo que hizo bien y presenta el
  EJERCICIO ACTIVO, sin mostrar el procedimiento.
- conceptual_challenge: pide una justificación o una aplicación equivalente.
"""

HINT_LADDER = {
    0: "Ayuda máxima permitida: NINGUNA. Solo una pregunta abierta.",
    1: "Ayuda máxima permitida: una pregunta orientadora, sin dar la idea "
       "(ej. '¿qué operación deshace la multiplicación?').",
    2: "Ayuda máxima permitida: una pista conceptual (la idea), sin pasos.",
    3: "Ayuda máxima permitida: un ejemplo análogo con OTROS números.",
    4: "Ayuda máxima permitida: resolver UN paso parcial y pedir el siguiente.",
}

VALIDATION_RULES = {
    "correct": "El valor final del estudiante es CORRECTO. No lo cuestiones. "
               "Reconoce lo que hizo bien describiendo su evidencia.",
    "incorrect": "El valor final del estudiante es INCORRECTO. No reveles la "
                 "solución; ayúdalo a revisar su razonamiento con una pregunta.",
    "unrecognized": "No se pudo leer un valor final. No asumas que es "
                    "correcto ni incorrecto; pídele su respuesta o su paso.",
}


def _claims_rule(state: PedagogicalState) -> str:
  if state.min_confidence() < 0.7:
    return (
        "LÍMITE DE AFIRMACIONES: la evidencia aún es limitada. NO digas que "
        "domina el tema ni uses 'excelente, lo entiendes todo'. Describe lo "
        "observado ('en tu respuesta mostraste que...')."
    )
  return (
      "LÍMITE DE AFIRMACIONES: puedes reconocer dominio con matices y "
      "citando evidencia concreta."
  )


def _profile_summary(state: PedagogicalState) -> str:
  profile = state.profile
  if not profile:
    return "Sin perfil todavía."
  strengths = [s["area"] for s in profile.get("strengths", [])]
  difficulties = [d["area"] for d in profile.get("difficulties", [])]
  hypotheses = [
      f"{h['label']} (confianza {h['confidence_quality']})"
      for h in profile.get("difficulty_hypotheses", [])
  ]
  return (
      f"Fortalezas: {strengths or 'ninguna clara'}. "
      f"Dificultades: {difficulties or 'ninguna clara'}. "
      f"Hipótesis a vigilar: {hypotheses or 'ninguna'}."
  )


def generate_tutor_response(
    client: Any,
    model_id: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
    answer_validation: dict[str, Any] | None = None,
    outcome: str = "neutral",
) -> str:
  validation_rule = (
      VALIDATION_RULES[answer_validation["status"]]
      if answer_validation
      else "No hay valor final que validar en este mensaje."
  )
  context = (
      f"{TUTOR_PROMPT}\n"
      f"ESTRATEGIA ACTUAL: {state.teaching_strategy}\n"
      f"NIVEL DE ANDAMIAJE (0 mínimo, 3 máximo): {state.scaffolding_level}\n"
      f"NIVEL DE PISTAS: {state.hint_level}. "
      f"{HINT_LADDER[state.hint_level]}\n"
      f"RESULTADO DEL ÚLTIMO TURNO: {outcome}\n"
      f"EJERCICIO ACTIVO: {state.active_exercise_statement}\n"
      f"PERFIL DEL DIAGNÓSTICO: {_profile_summary(state)}\n"
      f"{_claims_rule(state)}\n"
      f"CONTEXTO PEDAGÓGICO:\n"
      f"{json.dumps(state.as_prompt_context(), ensure_ascii=False)}\n\n"
      f"VALIDACIÓN MATEMÁTICA: {validation_rule}\n"
      f"EVIDENCIA QUE DEBES OBTENER: {state.next_step}"
  )
  try:
    response = client.converse(
        modelId=model_id,
        system=[{"text": context}],
        messages=conversation,
        inferenceConfig={"temperature": 0.3, "maxTokens": 600, "topP": 0.9},
    )
  except ClientError as exc:
    error_msg = exc.response.get("Error", {}).get("Message", str(exc))
    raise RuntimeError(f"Error al generar la tutoría en Bedrock: {error_msg}") from exc

  reply = "".join(
      block["text"]
      for block in response.get("output", {}).get("message", {}).get("content", [])
      if isinstance(block, dict) and isinstance(block.get("text"), str)
  ).strip()
  if not reply:
    raise RuntimeError("El tutor no devolvió una respuesta de texto.")
  return reply