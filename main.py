import copy
import json
import os
from typing import Any

import boto3
from dotenv import load_dotenv

from app.ai.evaluator import evaluate_student
from app.ai.tutor import generate_tutor_response
from app.core.answer_validator import validate_linear_answer
from app.core.exercise_manager import activate_exercise, select_exercise
from app.core.pedagogical_engine import (
    update_pedagogical_state,
    verify_transfer,
)
from app.core.state import PedagogicalState

load_dotenv()


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
  transfer_was_verified = working_state.transfer_verified
  conversation.append({"role": "user", "content": [{"text": prompt}]})

  try:
    validation = None
    if working_state.expected_value is not None:
      validation = validate_linear_answer(
          prompt, working_state.expected_value
      )
    validation_data = (
        {
            "status": validation.status,
            "student_value": validation.student_value,
            "justification_detected": validation.justification_detected,
        }
        if validation
        else None
    )
    evaluation = evaluate_student(
        client=client,
        model_id=model_id,
        conversation=conversation,
        state=working_state,
        answer_validation=validation_data,
    )
    verify_transfer(working_state, validation_data)
    if (
        evaluation["student_intent"] == "requesting_practice"
        or transfer_was_verified
    ):
      next_exercise = select_exercise(
          current_exercise_id=working_state.active_exercise_id,
          current_difficulty=working_state.exercise_difficulty,
          skill=working_state.concept,
      )
      activate_exercise(working_state, next_exercise)
    update_pedagogical_state(working_state, evaluation)
    reply = generate_tutor_response(
        client=client,
        model_id=model_id,
        prompt=prompt,
        conversation=conversation,
        state=working_state,
        answer_validation=validation_data,
    )
  except RuntimeError:
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
  default_model = os.getenv(
      "BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"
  )
  conversation: list[dict[str, Any]] = []
  pedagogical_state = PedagogicalState()
  activate_exercise(
      pedagogical_state,
      select_exercise(None, 0, pedagogical_state.concept),
  )

  print("Kaanbal está listo. Escribe 'salir' para terminar.")
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
    except RuntimeError as exc:
      print(f"\nNo se pudo procesar el mensaje: {exc}")
      continue
    print(f"\nKaanbal: {answer}")
    print(
        "\n[DEBUG - ESTADO PEDAGÓGICO]\n"
        f"{json.dumps(pedagogical_state.as_prompt_context(), ensure_ascii=False)}"
    )
