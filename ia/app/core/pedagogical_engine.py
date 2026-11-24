from typing import Any

from app.core.state import Estimate, Hypothesis, PedagogicalState


STRATEGIES = {
    "diagnostic_question",
    "concrete_representation",
    "visual_representation",
    "guided_explanation",
    "independent_practice",
    "conceptual_challenge",
}
DIMENSIONS = ("procedural", "conceptual", "relational")
LEVEL_VALUE = {"none": 0.0, "weak": 0.25, "partial": 0.55, "strong": 0.9}
HYPOTHESIS_DIMENSION = {
    "rule_without_reason": "conceptual",
    "no_justification": "conceptual",
    "confuses_equality_meaning": "relational",
    "treats_x_as_label": "relational",
}
HELP_INTENTS = {
    "expressing_confusion",
    "requesting_explanation",
    "asking_question",
}


# ---------------------------------------------------------------- estimaciones
def update_estimate(
    estimate: Estimate, level: str, quote: str, turn: int, hint_level: int
) -> None:
  """Actualiza score y confianza. La evidencia obtenida con ayuda pesa menos."""
  if level not in LEVEL_VALUE:
    return  # not_observed: no se inventa evidencia
  observed = LEVEL_VALUE[level]
  weight = max(0.3, 1 - 0.2 * hint_level)
  estimate.history.append(observed)
  n = len(estimate.history)
  alpha = max(0.25, 1 / (n + 1)) * weight
  estimate.score = round(estimate.score + alpha * (observed - estimate.score), 3)
  recent = estimate.history[-3:]
  spread = max(recent) - min(recent)  # inconsistencia baja la confianza
  estimate.confidence = round((n / (n + 2)) * (1 - 0.5 * spread), 2)
  estimate.quotes.append({"turn": turn, "level": level, "quote": quote})
  estimate.quotes = estimate.quotes[-5:]


# ----------------------------------------------------------------- hipótesis
def update_hypotheses(
    state: PedagogicalState,
    evaluation: dict[str, Any],
    validation: dict[str, Any] | None,
) -> None:
  seen = {error["label"] for error in evaluation["errors"]}
  for error in evaluation["errors"]:
    hypothesis = state.hypotheses.setdefault(
        error["label"], Hypothesis(error["label"])
    )
    hypothesis.status = "active"
    hypothesis.evidence.append(
        {"turn": state.turn_count, "quote": error["quote"]}
    )
    hypothesis.evidence = hypothesis.evidence[-5:]
    hypothesis.confidence = min(
        0.95, hypothesis.confidence + (1 - hypothesis.confidence) * 0.3
    )

  # Contra-evidencia: si la dimensión relacionada con la hipótesis se muestra
  # bien en este turno y el error no aparece, la hipótesis pierde confianza.
  for label, hypothesis in state.hypotheses.items():
    if hypothesis.status != "active" or label in seen:
      continue
    dimension = HYPOTHESIS_DIMENSION.get(label, "procedural")
    level = evaluation["dimensions"][dimension]["level"]
    if dimension == "procedural" and level == "partial" and not (
        validation is not None and validation["status"] == "correct"
    ):
      continue
    factor = {"strong": 0.6, "partial": 0.8}.get(level)
    if factor is None:
      continue
    hypothesis.confidence = round(hypothesis.confidence * factor, 3)
    if hypothesis.confidence < 0.15:
      hypothesis.status = "refuted"


# ------------------------------------------------------------ resultado / apoyo
def judge_outcome(
    evaluation: dict[str, Any], validation: dict[str, Any] | None
) -> str:
  levels = [
      d["level"]
      for d in evaluation["dimensions"].values()
      if d["level"] != "not_observed"
  ]
  status = validation["status"] if validation else None
  if (
      status == "incorrect"
      or evaluation["errors"]
      or any(level in {"none", "weak"} for level in levels)
  ):
    return "poor"
  if levels and all(level in {"partial", "strong"} for level in levels):
    return "good"
  return "neutral"


def update_support(
    state: PedagogicalState, outcome: str, asked_for_help: bool
) -> None:
  """Pista y andamiaje dependen del desempeño, no del número de turnos."""
  if outcome == "poor" or asked_for_help:
    state.consecutive_failures += 1
    state.hint_level = min(4, state.hint_level + 1)
    if state.consecutive_failures >= 2:
      state.scaffolding_level = min(3, state.scaffolding_level + 1)
  elif outcome == "good":
    state.consecutive_failures = 0
    if state.hint_level <= 1:
      state.scaffolding_level = max(0, state.scaffolding_level - 1)  # fading


# ------------------------------------------------------------------ estrategia
def select_strategy(
    state: PedagogicalState,
    evaluation: dict[str, Any],
    outcome: str,
    validation: dict[str, Any] | None,
) -> str:
  intent = evaluation["student_intent"]
  conceptual_level = evaluation["dimensions"]["conceptual"]["level"]
  correct = validation is not None and validation["status"] == "correct"

  if correct:
    justified = conceptual_level in {"partial", "strong"}
    if justified and state.conceptual.confidence >= 0.4:
      return "independent_practice"
    return "conceptual_challenge"
  if intent == "requesting_practice":
    return "independent_practice" if state.exercise_solved else "diagnostic_question"
  if intent in {"requesting_explanation", "asking_question"}:
    return "guided_explanation"
  if outcome == "poor" or intent == "expressing_confusion":
    if state.consecutive_failures <= 1:
      return "diagnostic_question"
    if state.consecutive_failures == 2:
      return "concrete_representation"
    if state.consecutive_failures == 3:
      return "visual_representation"
    return "guided_explanation"
  if state.min_confidence() < 0.4:
    return "diagnostic_question"  # falta evidencia: pedir más
  return "conceptual_challenge"


NEXT_STEP = {
    "diagnostic_question": "Obtener más evidencia sobre su razonamiento.",
    "concrete_representation": "Relacionar el concepto con un ejemplo concreto.",
    "visual_representation": "Interpretar una representación visual.",
    "guided_explanation": "Justificar el siguiente paso con apoyo gradual.",
    "independent_practice": "Resolver el nuevo ejercicio sin procedimiento dado.",
    "conceptual_challenge": "Justificar por qué se realiza la operación elegida.",
}


# ----------------------------------------------------------------- actualización
def update_pedagogical_state(
    state: PedagogicalState,
    evaluation: dict[str, Any],
    validation: dict[str, Any] | None,
) -> tuple[str, str]:
  """Aplica la evaluación al estado. Devuelve (estrategia, resultado)."""
  state.turn_count += 1
  if validation is not None and validation["status"] in {"correct", "incorrect"}:
    state.attempt_count += 1
  in_practice = state.phase == "practice"
  if in_practice and validation is not None and validation["status"] == "correct":
    state.exercise_solved = True

  weight_hint = state.hint_level if in_practice else 0
  for name in DIMENSIONS:
    dimension = evaluation["dimensions"][name]
    update_estimate(
        getattr(state, name),
        dimension["level"],
        dimension["quote"],
        state.turn_count,
        weight_hint,
    )
  update_hypotheses(state, evaluation, validation)
  for label in evaluation["strategies_used"]:
    state.strategies_used[label] = state.strategies_used.get(label, 0) + 1

  state.learning_evidence.append(
      {
          "turn": state.turn_count,
          "intent": evaluation["student_intent"],
          "levels": {
              n: evaluation["dimensions"][n]["level"] for n in DIMENSIONS
          },
          "errors": [e["label"] for e in evaluation["errors"]],
          "validation": validation["status"] if validation else None,
      }
  )
  state.learning_evidence = state.learning_evidence[-10:]

  outcome = judge_outcome(evaluation, validation)
  if not in_practice:
    return "diagnostic_question", outcome

  update_support(state, outcome, evaluation["student_intent"] in HELP_INTENTS)
  strategy = select_strategy(state, evaluation, outcome, validation)
  if strategy not in STRATEGIES:
    raise ValueError(f"Estrategia pedagógica no permitida: {strategy}")
  state.teaching_strategy = strategy
  state.strategy_history = (state.strategy_history + [strategy])[-5:]
  state.next_step = NEXT_STEP[strategy]
  return strategy, outcome


def verify_transfer(
    state: PedagogicalState,
    evaluation: dict[str, Any],
    validation: dict[str, Any] | None,
) -> None:
  """Se llama DESPUÉS de actualizar el estado del turno."""
  if (
      state.exercise_difficulty >= 2
      and validation is not None
      and validation["status"] == "correct"
      and evaluation["dimensions"]["conceptual"]["level"]
      in {"partial", "strong"}
      and state.hint_level <= 1
  ):
    state.transfer_verified = True
    state.transfers_verified += 1


# ---------------------------------------------------------------------- perfil
def confidence_quality(value: float) -> str:
  if value < 0.4:
    return "baja"
  if value < 0.7:
    return "media"
  return "alta"


def build_profile(state: PedagogicalState) -> dict[str, Any]:
  strengths: list[dict[str, Any]] = []
  difficulties: list[dict[str, Any]] = []
  for name, estimate in state.estimates().items():
    if estimate.confidence < 0.3:
      continue  # sin evidencia suficiente no se concluye nada
    entry = {
        "area": name,
        "score": estimate.score,
        "confidence": estimate.confidence,
        "confidence_quality": confidence_quality(estimate.confidence),
        "evidence": estimate.quotes[-3:],
    }
    if estimate.score >= 0.6:
      strengths.append(entry)
    elif estimate.score <= 0.4:
      difficulties.append(entry)

  hypotheses = [
      {
          "label": h.label,
          "confidence": round(h.confidence, 2),
          "confidence_quality": confidence_quality(h.confidence),
          "evidence": h.evidence[-3:],
      }
      for h in state.hypotheses.values()
      if h.status == "active" and h.confidence >= 0.3
  ]
  hypotheses.sort(key=lambda h: h["confidence"], reverse=True)

  overall = round(
      sum(e.confidence for e in state.estimates().values()) / 3, 2
  )
  return {
      "strengths": strengths,
      "difficulties": difficulties,
      "difficulty_hypotheses": hypotheses,
      "strategies_used": dict(state.strategies_used),
      "overall_confidence": overall,
      "overall_confidence_quality": confidence_quality(overall),
  }