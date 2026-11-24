from dataclasses import dataclass

from ia.app.core.state import PedagogicalState


@dataclass(frozen=True)
class DiagnosticItem:
  id: str
  question: str
  probes: str  # conocimiento previo o habilidad que explora
  expected_errors: tuple[str, ...]
  expected_value: float | None = None


DIAGNOSTIC_ITEMS = (
    DiagnosticItem(
        "d1",
        "Un número multiplicado por 3 da 15. ¿Cuál es ese número y cómo lo "
        "supiste?",
        "relación entre multiplicación y división",
        ("wrong_inverse_operation", "no_justification"),
        5,
    ),
    DiagnosticItem(
        "d2",
        "¿Cómo resolverías 2x + 4 = 10? Cuéntame qué haces primero y por qué.",
        "orden de operaciones inversas con dos pasos",
        ("order_of_steps_error", "operates_one_side_only", "sign_error"),
        3,
    ),
    DiagnosticItem(
        "d3",
        "Un compañero dice que en 3x = 15, x = 45 porque 3 × 15 = 45. "
        "¿Qué opinas de su razonamiento?",
        "detección de errores y operación inversa",
        ("wrong_inverse_operation",),
        None,  # es una crítica: no hay un valor final que validar
    ),
    DiagnosticItem(
        "d4",
        "¿Qué significa que los dos lados de una ecuación sean iguales? "
        "Dame un ejemplo con tus palabras.",
        "significado de la igualdad y equilibrio",
        ("confuses_equality_meaning", "treats_x_as_label"),
        None,
    ),
)

NEUTRAL_ACKNOWLEDGMENTS = (
    "Gracias por explicarlo.",
    "Entiendo tu idea, gracias.",
    "Gracias, eso me ayuda a conocer cómo piensas.",
    "Perfecto, tomo nota.",
)

DIMENSION_TEXT = {
    "procedural": "resolver ecuaciones paso a paso",
    "conceptual": "explicar por qué funcionan los pasos",
    "relational": "relacionar ideas (igualdad, operaciones inversas)",
}

ERROR_TEXT = {
    "operates_one_side_only": "hacer la misma operación en los dos lados",
    "wrong_inverse_operation": "elegir la operación inversa correcta",
    "sign_error": "cuidar los signos",
    "treats_x_as_label": "ver la x como un número desconocido",
    "arithmetic_slip": "revisar las cuentas",
    "no_justification": "explicar el porqué de cada paso",
    "confuses_equality_meaning": "el significado de la igualdad",
    "order_of_steps_error": "el orden de los pasos",
    "rule_without_reason": "explicar por qué funciona 'pasar al otro lado'",
}


def intro_message() -> str:
  return (
      "Hola, soy Kaanbal. Antes de practicar quiero conocer cómo piensas, "
      "así que te haré unas preguntas cortas. No hay respuestas malas: "
      "me sirve más tu razonamiento que el resultado.\n\n"
      f"{DIAGNOSTIC_ITEMS[0].question}"
  )


def set_diagnostic_item(state: PedagogicalState, item: DiagnosticItem) -> None:
  state.expected_value = item.expected_value
  state.active_exercise_id = item.id
  state.active_exercise_statement = item.question
  state.exercise_difficulty = 0
  state.next_step = f"Explorar: {item.probes}"


def acknowledgment(evaluation: dict, index: int) -> str:
  dims = evaluation["dimensions"].values()
  levels = [d["level"] for d in dims if d["level"] != "not_observed"]
  # Se decide por la evidencia, no por el intent (que el LLM clasifica mal).
  if levels and all(level == "none" for level in levels):
    return (
        "Gracias por ser sincero, eso me ayuda mucho. No pasa nada si aún "
        "no lo tienes claro."
    )
  return NEUTRAL_ACKNOWLEDGMENTS[index % len(NEUTRAL_ACKNOWLEDGMENTS)]


def reask_message(evaluation: dict, item: DiagnosticItem) -> str:
  if evaluation["student_intent"] in {"asking_question", "requesting_explanation"}:
    prefix = "Buena pregunta, la retomamos al terminar estas preguntas."
  else:
    prefix = "Todavía no tengo suficiente para entender cómo piensas."
  return (
      f"{prefix} Cuéntame tu idea con tus palabras, aunque no estés seguro:"
      f"\n\n{item.question}"
  )


def profile_message(profile: dict, exercise_statement: str) -> str:
  strengths = [DIMENSION_TEXT[s["area"]] for s in profile["strengths"]]
  difficulties = [DIMENSION_TEXT[d["area"]] for d in profile["difficulties"]]
  difficulties += [
      ERROR_TEXT[h["label"]]
      for h in profile["difficulty_hypotheses"]
      if h["label"] in ERROR_TEXT
  ]
  difficulties = list(dict.fromkeys(difficulties))

  lines = [
      "Gracias, ya tengo una primera idea de cómo piensas. Son solo "
      "hipótesis y las iré ajustando mientras practicamos."
  ]
  if strengths:
    lines.append("Parece que se te da bien: " + ", ".join(strengths) + ".")
  if difficulties:
    lines.append("Podemos reforzar: " + ", ".join(difficulties) + ".")
  lines.append(
      f"Vamos con un ejercicio. Cuéntame cada paso y por qué lo das:\n\n"
      f"{exercise_statement}"
  )
  return "\n\n".join(lines)