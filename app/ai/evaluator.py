import json
from typing import Any

from botocore.exceptions import ClientError

from app.core.state import PedagogicalState


EVALUATOR_PROMPT = """
Eres un evaluador pedagógico especializado en matemáticas.
Tu trabajo es interpretar el comportamiento del estudiante, no enseñar ni
resolver ejercicios. Analiza principalmente el último mensaje considerando
el historial y el estado pedagógico.

NO enseñes, NO resuelvas ejercicios, NO felicites y NO inventes conocimientos.
No confundas una respuesta correcta con comprensión demostrada y no clasifiques
como incorrecta una respuesta sin evidencia matemática.
Devuelve únicamente JSON válido con esta forma:
{
  "student_intent": "asking_question|expressing_confusion|giving_answer|showing_procedure|requesting_explanation|requesting_practice|confirming_understanding|other",
  "understanding_signal": "demonstrated|partial|insufficient|incorrect|unknown",
  "evidence": ["evidencias observables"],
  "misconception_hypotheses": ["hipótesis respaldadas por el mensaje"],
  "skill": "habilidad matemática involucrada"
}
"""

VALID_INTENTS = {
    "asking_question",
    "expressing_confusion",
    "giving_answer",
    "showing_procedure",
    "requesting_explanation",
    "requesting_practice",
    "confirming_understanding",
    "other",
}
VALID_SIGNALS = {"demonstrated", "partial", "insufficient", "incorrect", "unknown"}


def _response_text(response: dict[str, Any]) -> str:
  return "".join(
      block["text"]
      for block in response.get("output", {}).get("message", {}).get("content", [])
      if isinstance(block, dict) and isinstance(block.get("text"), str)
  ).strip()


def _parse_evaluation(text: str) -> dict[str, Any]:
  normalized = text.strip()
  if normalized.startswith("```"):
    lines = normalized.splitlines()
    normalized = "\n".join(lines[1:-1]).strip()
  if not normalized:
    raise ValueError("La respuesta del evaluador está vacía.")

  object_start = normalized.find("{")
  object_end = normalized.rfind("}")
  if object_start == -1 or object_end <= object_start:
    raise ValueError("La respuesta no contiene un objeto JSON.")

  evaluation = json.loads(normalized[object_start:object_end + 1])
  if not isinstance(evaluation, dict):
    raise ValueError("El JSON del evaluador no es un objeto.")
  return evaluation


def _request_evaluation(
    client: Any,
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
) -> str:
  try:
    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=messages,
        inferenceConfig={"temperature": 0.0, "maxTokens": 512, "topP": 0.9},
    )
  except ClientError as exc:
    error_msg = exc.response.get("Error", {}).get("Message", str(exc))
    raise RuntimeError(f"Error al evaluar el mensaje en Bedrock: {error_msg}") from exc
  return _response_text(response)


def evaluate_student(
    client: Any,
    model_id: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
    answer_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
  evaluator_context = (
      f"{EVALUATOR_PROMPT}\n\n"
      f"ESTADO PEDAGÓGICO:\n"
      f"{json.dumps(state.as_prompt_context(), ensure_ascii=False)}\n\n"
      f"VALIDACIÓN MATEMÁTICA:\n"
      f"{json.dumps(answer_validation, ensure_ascii=False)}"
  )
  response_text = _request_evaluation(
      client, model_id, evaluator_context, conversation
  )
  try:
    evaluation = _parse_evaluation(response_text)
  except (json.JSONDecodeError, ValueError):
    # A model can lose the requested format; retry without dropping context.
    response_text = _request_evaluation(
        client, model_id, evaluator_context, conversation
    )
    try:
      evaluation = _parse_evaluation(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
      raise RuntimeError(
          "El evaluador pedagógico no devolvió un JSON válido después de reintentar."
      ) from exc

  if evaluation.get("student_intent") not in VALID_INTENTS:
    raise RuntimeError("El evaluador devolvió una intención inválida.")
  if evaluation.get("understanding_signal") not in VALID_SIGNALS:
    raise RuntimeError("El evaluador devolvió una señal inválida.")
  if not isinstance(evaluation.get("skill"), str):
    raise RuntimeError("El evaluador no devolvió una habilidad válida.")

  for field_name in ("evidence", "misconception_hypotheses"):
    values = evaluation.get(field_name)
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
      raise RuntimeError(f"El evaluador devolvió {field_name} inválido.")
  if answer_validation:
    if answer_validation["status"] == "correct":
      evaluation["understanding_signal"] = "partial"
      evaluation["answer_status"] = "correct"
    elif answer_validation["status"] == "incorrect":
      evaluation["understanding_signal"] = "incorrect"
  return evaluation
