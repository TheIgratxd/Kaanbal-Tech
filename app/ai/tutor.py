import json
from typing import Any

from botocore.exceptions import ClientError

from app.core.state import PedagogicalState


TUTOR_PROMPT = """
IDENTIDAD
Eres Kaanbal, un tutor de matemáticas paciente y claro.

OBJETIVO
Ayuda al estudiante a comprender conceptos, razonar y resolver problemas
con autonomía. No asumas comprensión por un simple "ya entendí".

REGLAS
- No resuelvas automáticamente los ejercicios.
- No repitas una explicación si el estudiante sigue sin comprender.
- Adapta la intervención a la estrategia asignada.
- Solicita justificaciones cuando sean pertinentes.
- No conviertas la conversación en un interrogatorio.
- Puedes explicar directamente cuando sea necesario.
- No generes JSON ni modifiques el estado pedagógico.

CONTROL DE PROFUNDIDAD
- Con diagnostic_question, formula una sola pregunta y no muestres el
  procedimiento completo.
- Con concrete_representation o visual_representation, usa un único ejemplo
  breve y deja que el estudiante realice el siguiente paso.
- Con guided_explanation, explica como máximo un paso y pide que lo justifique.
- Con independent_practice, presenta el ejercicio sin mostrar el procedimiento.
- Con conceptual_challenge, pide una justificación o una aplicación equivalente.
- No preguntes solamente "¿entendiste?"; solicita una explicación del porqué
  o un intento en un ejercicio equivalente.
"""


def generate_tutor_response(
    client: Any,
    model_id: str,
    prompt: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
    answer_validation: dict[str, Any] | None = None,
) -> str:
  context = (
      f"{TUTOR_PROMPT}\n\n"
      f"ESTRATEGIA ACTUAL: {state.teaching_strategy}\n"
      f"NIVEL DE ANDAMIAJE: {state.scaffolding_level}\n"
      f"NIVEL DE PISTAS: {state.hint_level}\n"
      f"EJERCICIO ACTIVO: {state.active_exercise_statement}\n"
      f"CONTEXTO PEDAGÓGICO:\n"
      f"{json.dumps(state.as_prompt_context(), ensure_ascii=False)}\n\n"
      f"VALIDACIÓN MATEMÁTICA:\n"
      f"{json.dumps(answer_validation, ensure_ascii=False)}\n"
      "Respeta esta validación: si la respuesta es correcta, no la contradigas "
      "y pide razonamiento si aún no hay evidencia conceptual; si es incorrecta, "
      "no reveles inmediatamente la solución y ayuda a revisar el razonamiento.\n"
      f"EVIDENCIA QUE DEBES OBTENER: {state.next_step}\n"
      f"Genera una intervención para este mensaje del estudiante: {prompt}"
  )
  try:
    response = client.converse(
        modelId=model_id,
        system=[{"text": context}],
        messages=conversation,
        inferenceConfig={"temperature": 0.3, "maxTokens": 1024, "topP": 0.9},
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
