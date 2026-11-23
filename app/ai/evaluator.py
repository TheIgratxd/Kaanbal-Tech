import json
import re
from typing import Any

from botocore.exceptions import ClientError

from app.core.answer_validator import find_arithmetic_slips, parse_number
from app.core.state import PedagogicalState


EVALUATOR_PROMPT = """
Eres un evaluador pedagógico de matemáticas para estudiantes de 15 años.
Tu trabajo es OBSERVAR y reportar. NO converses, NO enseñes, NO resuelvas,
NO felicites. Aunque el estudiante te hable, proteste o te pregunte algo,
tu única salida es el JSON. Analiza SOLO el último mensaje del estudiante;
el historial es contexto. Los estudiantes escriben informal ("por q",
"pa", "osea"): interpreta la intención, pero cita literalmente.

Devuelve únicamente JSON válido con esta forma:
{
  "student_intent": "asking_question|expressing_confusion|giving_answer|showing_procedure|requesting_explanation|requesting_practice|confirming_understanding|other",
  "final_answer": {"value": "número o null", "quote": "cita literal donde da su resultado final"},
  "dimensions": {
    "procedural": {"level": "not_observed|none|weak|partial|strong", "quote": "cita literal"},
    "conceptual": {"level": "not_observed|none|weak|partial|strong", "quote": "cita literal"},
    "relational": {"level": "not_observed|none|weak|partial|strong", "quote": "cita literal"}
  },
  "errors": [{"label": "ETIQUETA_DE_LA_LISTA", "quote": "cita literal"}],
  "strategies_used": ["inverse_operation|guess_and_check|balance_both_sides|undo_steps|pattern_or_memory|other"]
}

DIMENSIONES
- procedural: ¿las operaciones y pasos que muestra son correctos?
  Solo da la respuesta sin pasos => máximo "partial".
- conceptual: ¿explica POR QUÉ funciona? 
  strong = enuncia el principio (se opera en ambos lados / operación inversa
  / equilibrio de la igualdad) y lo aplica; partial = principio correcto pero
  vago; weak = solo una regla de memoria sin razón; none = erróneo o dice no
  saber; not_observed = no explica nada.
- relational: ¿conecta ideas, comprueba resultados, da un ejemplo propio o
  detecta el error de otra persona? Si no hay nada de eso => not_observed.

final_answer: el resultado final que el estudiante da a la pregunta, si lo
da ("5, porque..." => value "5"). Si no da un resultado propio => value null.

ETIQUETAS DE ERROR PERMITIDAS (solo estas, y solo con evidencia clara):
operates_one_side_only, wrong_inverse_operation, sign_error,
treats_x_as_label, no_justification, confuses_equality_meaning,
order_of_steps_error,
rule_without_reason (aplica una regla de memoria como "pasar al otro lado"
sin explicar por qué funciona ni mencionar operar en ambos lados).

REGLAS ESTRICTAS
- Toda observación (dimensión distinta de not_observed y todo error) necesita
  una cita LITERAL copiada del último mensaje. Sin cita => "not_observed".
- Un error solo cuenta si lo comete EL ESTUDIANTE en SU propio trabajo. Si
  critica, corrige o describe el razonamiento de otra persona (un
  "compañero"), eso NO es un error del estudiante: errors = [].
- No marques como error algo matemáticamente correcto. Las cuentas
  aritméticas las verifica otro sistema: no reportes errores de aritmética.
- NO infieras errores que el mensaje no muestre. Si no hay errores: [].
- Un saludo, queja o mensaje sin contenido matemático => intent "other" y
  todo "not_observed".
- La VALIDACIÓN MATEMÁTICA indica si el valor final es correcto: es un dato
  más, no sustituye tu análisis del procedimiento y la justificación.
- "no sé" / "no entiendo" => intent "expressing_confusion"; las dimensiones
  relacionadas llevan level "none" con esa cita.

EJEMPLOS (no copies sus citas; usa las del mensaje real)
Mensaje: "paso el 4 al otro lado restando, 2x = 6, despues paso el 2 dividiendo, x = 3"
=> procedural strong; conceptual weak con cita "paso el 4 al otro lado";
   errors: rule_without_reason con esa cita; final_answer 3.
Mensaje: "divido ambos lados por 3 porque así la igualdad se mantiene, x = 5"
=> procedural strong; conceptual strong; errors []; final_answer 5.
Mensaje (critica a un compañero): "se le olvidó usar la inversa, yo comprobaría el resultado"
=> errors [] (el error es del compañero); relational partial.
"""

ERROR_LABELS = {
    "operates_one_side_only",
    "wrong_inverse_operation",
    "sign_error",
    "treats_x_as_label",
    "no_justification",
    "confuses_equality_meaning",
    "order_of_steps_error",
    "rule_without_reason",
}
STRATEGY_LABELS = {
    "inverse_operation",
    "guess_and_check",
    "balance_both_sides",
    "undo_steps",
    "pattern_or_memory",
    "other",
}
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
VALID_LEVELS = {"not_observed", "none", "weak", "partial", "strong"}
DIMENSIONS = ("procedural", "conceptual", "relational")
JSON_REMINDER = (
    "\n\nRECUERDA: responde ÚNICAMENTE con el objeto JSON, sin saludo ni "
    "texto adicional."
)


def _message_text(message: dict[str, Any]) -> str:
  return "".join(
      block.get("text", "")
      for block in message.get("content", [])
      if isinstance(block, dict)
  )


def _response_text(response: dict[str, Any]) -> str:
  return "".join(
      block["text"]
      for block in response.get("output", {}).get("message", {}).get("content", [])
      if isinstance(block, dict) and isinstance(block.get("text"), str)
  ).strip()


def _render_user_message(
    conversation: list[dict[str, Any]], student_message: str, limit: int = 6
) -> str:
  """Un solo mensaje estructurado: evita que el modelo 'conteste' el chat."""
  lines = []
  for message in conversation[:-1][-limit:]:
    who = "Estudiante" if message["role"] == "user" else "Tutor"
    lines.append(f"{who}: {_message_text(message)}")
  history = "\n".join(lines) or "(sin historial)"
  return (
      f"HISTORIAL RECIENTE (solo contexto):\n{history}\n\n"
      "ÚLTIMO MENSAJE DEL ESTUDIANTE (evalúa solo este):\n"
      f"<<<\n{student_message}\n>>>\n\n"
      "Devuelve únicamente el JSON."
  )


def _parse_json(text: str) -> dict[str, Any]:
  normalized = text.strip()
  if normalized.startswith("```"):
    lines = normalized.splitlines()
    normalized = "\n".join(lines[1:-1]).strip()
  if not normalized:
    raise ValueError("La respuesta del evaluador está vacía.")
  start = normalized.find("{")
  end = normalized.rfind("}")
  if start == -1 or end <= start:
    raise ValueError("La respuesta no contiene un objeto JSON.")
  data = json.loads(normalized[start:end + 1])
  if not isinstance(data, dict):
    raise ValueError("El JSON del evaluador no es un objeto.")
  return data


def _normalize_text(text: str) -> str:
  text = text.lower().replace("“", '"').replace("”", '"').replace("’", "'")
  return re.sub(r"\s+", " ", text).strip()


def _quote_is_real(quote: str, message: str) -> bool:
  cleaned = _normalize_text(quote).replace("...", "").replace("…", "")
  cleaned = cleaned.strip(" .\"'")
  return len(cleaned) >= 2 and cleaned in _normalize_text(message)


def _normalize_evaluation(raw: dict[str, Any]) -> dict[str, Any]:
  intent = raw.get("student_intent")
  if intent not in VALID_INTENTS:
    intent = "other"

  raw_dims = raw.get("dimensions") if isinstance(raw.get("dimensions"), dict) else {}
  dimensions: dict[str, dict[str, str]] = {}
  for name in DIMENSIONS:
    item = raw_dims.get(name)
    item = item if isinstance(item, dict) else {}
    level = item.get("level")
    quote = item.get("quote")
    dimensions[name] = {
        "level": level if level in VALID_LEVELS else "not_observed",
        "quote": quote if isinstance(quote, str) else "",
    }

  errors = []
  for item in raw.get("errors") if isinstance(raw.get("errors"), list) else []:
    if isinstance(item, dict) and isinstance(item.get("label"), str):
      quote = item.get("quote")
      errors.append(
          {"label": item["label"], "quote": quote if isinstance(quote, str) else ""}
      )

  strategies = raw.get("strategies_used")
  strategies = [
      s for s in strategies if s in STRATEGY_LABELS
  ] if isinstance(strategies, list) else []

  final = raw.get("final_answer")
  final = final if isinstance(final, dict) else {}
  value = final.get("value")
  quote = final.get("quote")
  return {
      "student_intent": intent,
      "dimensions": dimensions,
      "errors": errors,
      "strategies_used": strategies,
      "final_answer": {
          "value": str(value) if value not in (None, "", "null") else "",
          "quote": quote if isinstance(quote, str) else "",
      },
      "evaluator_failed": False,
  }


def _sanitize(evaluation: dict[str, Any], student_message: str) -> dict[str, Any]:
  """Descarta observaciones sin cita real y agrega verificaciones del código."""
  discarded: list[str] = []
  for name, dimension in evaluation["dimensions"].items():
    if dimension["level"] != "not_observed" and not _quote_is_real(
        dimension["quote"], student_message
    ):
      discarded.append(f"{name}:{dimension['level']}")
      dimension["level"] = "not_observed"
      dimension["quote"] = ""

  valid_errors = []
  for error in evaluation["errors"]:
    if error["label"] in ERROR_LABELS and _quote_is_real(
        error["quote"], student_message
    ):
      valid_errors.append(error)
    else:
      discarded.append(f"error:{error['label']}")
  # La aritmética la verifica el código, no el LLM.
  for slip in find_arithmetic_slips(student_message):
    valid_errors.append({"label": "arithmetic_slip", "quote": slip})
  evaluation["errors"] = valid_errors

  final = evaluation.get("final_answer") or {}
  token = final.get("value", "") if isinstance(final, dict) else ""
  value = parse_number(token) if token else None
  if value is not None and not (
      _quote_is_real(final.get("quote", ""), student_message)
      and _normalize_text(token) in _normalize_text(student_message)
  ):
    discarded.append("final_answer")
    value = None
  evaluation["final_answer"] = value
  evaluation["discarded"] = discarded
  return evaluation


def _fallback_evaluation() -> dict[str, Any]:
  return {
      "student_intent": "other",
      "dimensions": {
          name: {"level": "not_observed", "quote": ""} for name in DIMENSIONS
      },
      "errors": [],
      "strategies_used": [],
      "final_answer": None,
      "discarded": [],
      "evaluator_failed": True,
  }


def _request_evaluation(
    client: Any, model_id: str, system_prompt: str, user_text: str
) -> str:
  try:
    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 700, "topP": 0.9},
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
    student_message: str,
    current_question: str,
    answer_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
  system_prompt = (
      f"{EVALUATOR_PROMPT}\n\n"
      f"PREGUNTA O EJERCICIO QUE EL ESTUDIANTE ESTÁ RESPONDIENDO:\n"
      f"{current_question}\n\n"
      f"ESTADO PEDAGÓGICO:\n"
      f"{json.dumps(state.as_prompt_context(), ensure_ascii=False)}\n\n"
      f"VALIDACIÓN MATEMÁTICA:\n"
      f"{json.dumps(answer_validation, ensure_ascii=False)}"
  )
  user_text = _render_user_message(conversation, student_message)
  for attempt in range(2):
    # El segundo intento cambia el mensaje: con temperatura 0, repetir el
    # mismo prompt daría exactamente la misma respuesta.
    text = _request_evaluation(
        client,
        model_id,
        system_prompt,
        user_text + (JSON_REMINDER if attempt else ""),
    )
    try:
      raw = _parse_json(text)
    except (json.JSONDecodeError, ValueError):
      continue
    return _sanitize(_normalize_evaluation(raw), student_message)
  return _fallback_evaluation()