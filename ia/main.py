import copy
import json
import os
from typing import Any

import boto3
from dotenv import load_dotenv

from ia.app.ai.evaluator import evaluate_student
from ia.app.ai.tutor import generate_tutor_response
from ia.app.core.answer_validator import validate_linear_answer
from ia.app.core.diagnostic import (
    DIAGNOSTIC_ITEMS,
    acknowledgment,
    intro_message,
    profile_message,
    reask_message,
    set_diagnostic_item,
)
from ia.app.core.exercise_manager import activate_exercise, select_exercise
from ia.app.core.pedagogical_engine import (
    build_profile,
    update_pedagogical_state,
    verify_transfer,
)
from ia.app.core.state import PedagogicalState

load_dotenv()


def _validate(prompt: str, state: PedagogicalState) -> dict[str, Any] | None:
  """Validación por regex (rápida). Puede quedar 'unrecognized'."""
  if state.expected_value is None:
    return None
  result = validate_linear_answer(prompt, state.expected_value)
  return {"status": result.status, "student_value": result.student_value}


def _resolve_validation(
    state: PedagogicalState,
    regex_validation: dict[str, Any] | None,
    evaluation: dict[str, Any],
) -> dict[str, Any] | None:
  """Si el regex no reconoce el resultado, usa la respuesta final que el
  evaluador extrajo (ya verificada con cita) y la compara el código."""
  if state.expected_value is None:
    return None
  if regex_validation and regex_validation["status"] != "unrecognized":
    return regex_validation
  value = evaluation.get("final_answer")
  if value is None:
    return regex_validation
  status = "correct" if abs(value - state.expected_value) < 1e-9 else "incorrect"
  return {"status": status, "student_value": value}


def _has_observation(evaluation: dict[str, Any]) -> bool:
  return bool(evaluation["errors"]) or any(
      d["level"] != "not_observed" for d in evaluation["dimensions"].values()
  )


def _finish_diagnostic(
    state: PedagogicalState, conversation: list[dict[str, Any]]
) -> str:
  """Cierra la fase 1, genera el perfil (fase 2) y activa el primer ejercicio."""
  profile = build_profile(state)
  state.profile = profile
  strong_procedure = state.procedural.score >= 0.7 and state.procedural.confidence >= 0.5
  exercise = select_exercise(None, 1 if strong_procedure else 0, state.concept)
  activate_exercise(state, exercise)
  state.phase = "practice"
  # El mensaje del tutor se agrega después: la práctica empieza un mensaje más
  # adelante. Así el tutor no imita el patrón de las preguntas diagnósticas.
  state.practice_start = len(conversation) + 1
  state.next_step = "Resolver el ejercicio justificando cada paso."
  return profile_message(profile, exercise.statement)


def _diagnostic_turn(
    client: Any,
    model_id: str,
    prompt: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
) -> str:
  item = DIAGNOSTIC_ITEMS[state.diagnostic_index]
  validation = _validate(prompt, state)
  evaluation = evaluate_student(
      client=client,
      model_id=model_id,
      conversation=conversation,
      state=state,
      student_message=prompt,
      current_question=item.question,
      answer_validation=validation,
  )
  if not _has_observation(evaluation):
    return reask_message(evaluation, item)  # no cuenta como evidencia

  validation = _resolve_validation(state, validation, evaluation)
  update_pedagogical_state(state, evaluation, validation)
  state.diagnostic_index += 1
  if state.diagnostic_index < len(DIAGNOSTIC_ITEMS):
    next_item = DIAGNOSTIC_ITEMS[state.diagnostic_index]
    set_diagnostic_item(state, next_item)
    return (
        f"{acknowledgment(evaluation, state.diagnostic_index)}\n\n"
        f"{next_item.question}"
    )
  return _finish_diagnostic(state, conversation)


def _tutor_history(
    conversation: list[dict[str, Any]], state: PedagogicalState
) -> list[dict[str, Any]]:
  history = conversation[state.practice_start:]
  if not history or history[0]["role"] != "user":
    history = conversation[-1:]
  return history


def _practice_turn(
    client: Any,
    model_id: str,
    prompt: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
) -> str:
  regex_validation = _validate(prompt, state)
  evaluation = evaluate_student(
      client=client,
      model_id=model_id,
      conversation=conversation,
      state=state,
      student_message=prompt,
      current_question=state.active_exercise_statement,
      answer_validation=regex_validation,
  )
  validation = _resolve_validation(state, regex_validation, evaluation)
  outcome = "neutral"
  presented_new_exercise = False
  if not evaluation.get("evaluator_failed"):
    strategy, outcome = update_pedagogical_state(state, evaluation, validation)
    verify_transfer(state, evaluation, validation)
    if strategy == "independent_practice":
      next_exercise = select_exercise(
          current_exercise_id=state.active_exercise_id,
          current_difficulty=state.exercise_difficulty,
          skill=state.concept,
      )
      activate_exercise(state, next_exercise)
      presented_new_exercise = True
  reply = generate_tutor_response(
      client=client,
      model_id=model_id,
      conversation=_tutor_history(conversation, state),
      state=state,
      answer_validation=validation,
      outcome=outcome,
  )
  if presented_new_exercise:
    equation = state.active_exercise_statement.split(":", 1)[-1].strip()
    if equation not in reply:
      # Red de seguridad: si el modelo no presentó el ejercicio, se agrega.
      reply += f"\n\n{state.active_exercise_statement}"
  return reply


def process_student_message(
    prompt: str,
    model_id: str,
    region: str,
    conversation: list[dict[str, Any]],
    pedagogical_state: PedagogicalState,
) -> str:
  client = boto3.client("bedrock-runtime", region_name=region)
  conversation_length = len(conversation)
  working_state = copy.deepcopy(pedagogical_state)
  conversation.append({"role": "user", "content": [{"text": prompt}]})

  try:
    if working_state.phase == "diagnostic":
      reply = _diagnostic_turn(
          client, model_id, prompt, conversation, working_state
      )
    else:
      reply = _practice_turn(
          client, model_id, prompt, conversation, working_state
      )
  except (RuntimeError, ValueError):
    del conversation[conversation_length:]
    raise

  pedagogical_state.__dict__.update(working_state.__dict__)
  conversation.append({"role": "assistant", "content": [{"text": reply}]})
  return reply


def run_converse(
    prompt: str,
    model_id: str,
    region: str,
    conversation: list[dict[str, Any]] | None = None,
    pedagogical_state: PedagogicalState | None = None,
) -> str:
  session_conversation = conversation if conversation is not None else []
  state = pedagogical_state or PedagogicalState()
  return process_student_message(
      prompt=prompt,
      model_id=model_id,
      region=region,
      conversation=session_conversation,
      pedagogical_state=state,
  )


if __name__ == "__main__":
  region_name = os.getenv("AWS_REGION", "us-east-1")
  default_model = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
  conversation: list[dict[str, Any]] = []
  pedagogical_state = PedagogicalState()
  set_diagnostic_item(pedagogical_state, DIAGNOSTIC_ITEMS[0])

  print("Kaanbal está listo. Escribe 'salir' para terminar.")
  print(f"\nKaanbal: {intro_message()}")
  while True:
    prompt = input("\nTú: ").strip()
    if prompt.lower() in {"salir", "exit", "quit"}:
      break
    if not prompt:
      continue

    try:
      answer = run_converse(
          prompt=prompt,
          model_id=default_model,
          region=region_name,
          conversation=conversation,
          pedagogical_state=pedagogical_state,
      )
    except (RuntimeError, ValueError) as exc:
      print(f"\nNo se pudo procesar el mensaje: {exc}")
      continue
    print(f"\nKaanbal: {answer}")
    print(
        "\n[DEBUG - ESTADO PEDAGÓGICO]\n"
        f"{json.dumps(pedagogical_state.debug_context(), ensure_ascii=False)}"
    )