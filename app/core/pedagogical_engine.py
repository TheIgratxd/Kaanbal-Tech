from typing import Any

from app.core.state import PedagogicalState


STRATEGIES = {
    "diagnostic_question",
    "concrete_representation",
    "visual_representation",
    "guided_explanation",
    "independent_practice",
    "conceptual_challenge",
}


def select_strategy(
    state: PedagogicalState, evaluation: dict[str, Any]
) -> str:
  signal = evaluation["understanding_signal"]
  intent = evaluation["student_intent"]

  if intent == "requesting_practice":
    return "independent_practice"
  if evaluation.get("answer_status") == "correct":
    return "conceptual_challenge"
  if intent == "requesting_explanation":
    return "guided_explanation"
  if intent == "expressing_confusion":
    if state.teaching_strategy == "diagnostic_question":
      return "concrete_representation"
    if state.teaching_strategy == "concrete_representation":
      return "visual_representation"
    return "guided_explanation"
  if signal == "incorrect":
    return "diagnostic_question"
  if signal == "insufficient":
    if state.teaching_strategy == "diagnostic_question":
      return "concrete_representation"
    if state.teaching_strategy == "concrete_representation":
      return "visual_representation"
    return "guided_explanation"
  if signal == "demonstrated":
    return "independent_practice"
  if intent == "confirming_understanding":
    return "conceptual_challenge"
  if intent == "asking_question":
    return "guided_explanation"
  return "diagnostic_question"


def _scaffolding_for(strategy: str) -> int:
  return {
      "diagnostic_question": 1,
      "concrete_representation": 3,
      "visual_representation": 2,
      "guided_explanation": 2,
      "independent_practice": 1,
      "conceptual_challenge": 0,
  }[strategy]


def update_pedagogical_state(
    state: PedagogicalState, evaluation: dict[str, Any]
) -> str:
  strategy = select_strategy(state, evaluation)
  if strategy not in STRATEGIES:
    raise ValueError(f"Estrategia pedagógica no permitida: {strategy}")

  intent = evaluation["student_intent"]
  state.turn_count += 1
  if intent in {"giving_answer", "showing_procedure"}:
    state.attempt_count += 1
  state.concept = evaluation["skill"]
  state.learning_evidence.append(
      {
          "turn": state.turn_count,
          "attempt": state.attempt_count,
          "signal": evaluation["understanding_signal"],
          "intent": evaluation["student_intent"],
          "evidence": evaluation["evidence"],
      }
  )
  state.learning_evidence = state.learning_evidence[-10:]
  if evaluation["misconception_hypotheses"]:
    state.misconception_hypotheses = list(
        dict.fromkeys(
            state.misconception_hypotheses
            + evaluation["misconception_hypotheses"]
        )
    )
  state.teaching_strategy = strategy
  state.scaffolding_level = _scaffolding_for(strategy)
  state.hint_level = min(4, state.hint_level + 1) if strategy != "diagnostic_question" else 0
  state.strategy_history.append(strategy)
  state.strategy_history = state.strategy_history[-5:]
  state.next_step = {
      "diagnostic_question": "Responder una pregunta sobre el prerrequisito.",
      "concrete_representation": "Relacionar el concepto con un ejemplo concreto.",
      "visual_representation": "Interpretar una representación visual del concepto.",
      "guided_explanation": "Justificar el siguiente paso con apoyo gradual.",
      "independent_practice": "Resolver un ejercicio similar sin procedimiento dado.",
      "conceptual_challenge": "Justificar por qué se realiza la operación elegida.",
  }[strategy]
  return strategy


def verify_transfer(
    state: PedagogicalState,
    answer_validation: dict[str, Any] | None,
) -> None:
  if (
      state.exercise_difficulty >= 2
      and answer_validation is not None
      and answer_validation.get("status") == "correct"
      and answer_validation.get("justification_detected") is True
      and state.hint_level <= 1
  ):
    state.transfer_verified = True
