
from __future__ import annotations

import copy
from dataclasses import asdict, is_dataclass
from typing import Any

import boto3
from dotenv import load_dotenv

from ia.app.ai.evaluator import evaluate_student
from ia.app.ai.tutor import generate_tutor_response

from ia.app.core.answer_validator import validate_linear_answer
from ia.app.core.diagnostic import (
    DIAGNOSTIC_ITEMS,
    acknowledgment,
    get_diagnostic_item,
    intro_message,
    profile_message,
    reask_message,
    set_diagnostic_item,
)
from ia.app.core.exercise_manager import (
    EXERCISES,
    activate_exercise,
    record_exercise_result,
    select_exercise,
    select_exercise_for_state,
)
from ia.app.core.pedagogical_engine import (
    build_profile,
    update_pedagogical_state,
    verify_transfer,
)
from ia.app.core.state import PedagogicalState


load_dotenv()


# ---------------------------------------------------------------------------
# Validación matemática
# ---------------------------------------------------------------------------

def _validation_to_dict(
    validation: Any,
) -> dict[str, Any]:
    if validation is None:
        return {
            "status": "unrecognized",
            "value": None,
        }

    if isinstance(validation, dict):
        return validation

    if is_dataclass(validation):
        return asdict(validation)

    if hasattr(validation, "__dict__"):
        return vars(validation)

    return {
        "status": "unrecognized",
        "value": None,
    }


def _validation_status(
    validation: dict[str, Any] | None,
) -> str:
    if not isinstance(validation, dict):
        return "unrecognized"

    status = validation.get("status")

    if status in {"correct", "incorrect", "unrecognized"}:
        return status

    if validation.get("is_correct") is True:
        return "correct"

    if validation.get("is_correct") is False:
        return "incorrect"

    return "unrecognized"


def _validate(
    prompt: str,
    state: PedagogicalState,
) -> dict[str, Any]:
    """
    Ejecuta la validación determinista cuando el ejercicio tiene
    un resultado esperado.
    """
    if state.expected_value is None:
        return {
            "status": "unrecognized",
            "value": None,
            "expected_value": None,
        }

    try:
        result = validate_linear_answer(
            prompt,
            state.expected_value,
        )

        validation = _validation_to_dict(result)

        validation.setdefault(
            "expected_value",
            state.expected_value,
        )

        return validation

    except (TypeError, ValueError, AttributeError):
        return {
            "status": "unrecognized",
            "value": None,
            "expected_value": state.expected_value,
        }


def _resolve_validation(
    validation: dict[str, Any],
    evaluation: dict[str, Any],
    expected_value: float | None,
) -> dict[str, Any]:
    """
    Prioriza la validación determinista.

    Si el validador no pudo reconocer la respuesta, utiliza el valor
    numérico extraído por el evaluador como segunda fuente.
    """
    status = _validation_status(validation)

    if status in {"correct", "incorrect"}:
        return {
            **validation,
            "status": status,
            "expected_value": expected_value,
        }

    final_answer = evaluation.get("final_answer")

    if expected_value is None or final_answer is None:
        return {
            **validation,
            "status": "unrecognized",
            "value": final_answer,
            "expected_value": expected_value,
        }

    try:
        student_value = float(final_answer)
        expected = float(expected_value)

    except (TypeError, ValueError):
        return {
            **validation,
            "status": "unrecognized",
            "value": final_answer,
            "expected_value": expected_value,
        }

    is_correct = abs(student_value - expected) < 1e-8

    return {
        **validation,
        "status": "correct" if is_correct else "incorrect",
        "value": student_value,
        "expected_value": expected,
        "source": "evaluator_fallback",
    }


# ---------------------------------------------------------------------------
# Comprobación de evidencia
# ---------------------------------------------------------------------------

def _has_observation(
    evaluation: dict[str, Any],
) -> bool:
    if evaluation.get("evaluator_failed"):
        return False

    dimensions = evaluation.get("dimensions", {})

    if isinstance(dimensions, dict):
        for item in dimensions.values():
            if not isinstance(item, dict):
                continue

            if item.get("level") != "not_observed":
                return True

    if evaluation.get("errors"):
        return True

    if evaluation.get("final_answer") is not None:
        return True

    return False


def _evaluate_turn(
    client: Any,
    model_id: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
    prompt: str,
    current_question: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    evaluation = evaluate_student(
        client=client,
        model_id=model_id,
        conversation=conversation,
        state=state,
        student_message=prompt,
        current_question=current_question,
        answer_validation=validation,
    )

    if evaluation.get("evaluator_failed"):
        raise RuntimeError(
            "El evaluador no pudo generar una evaluación válida. "
            "El estado pedagógico no será actualizado con información "
            "incompleta."
        )

    return evaluation


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------

def _finish_diagnostic(
    state: PedagogicalState,
    conversation: list[dict[str, Any]],
) -> str:
    """
    Finaliza el diagnóstico y activa el primer ejercicio.

    Se conserva una copia del perfil inicial para poder comparar
    el progreso posterior del estudiante.
    """
    state.profile = build_profile(state)
    state.diagnostic_profile = copy.deepcopy(state.profile)

    # Selección inicial de dificultad basada en la evidencia.
    procedural_score = state.procedural.score
    procedural_confidence = state.procedural.confidence

    if procedural_confidence < 0.3 or procedural_score < 0.4:
        initial_difficulty = 1
    elif procedural_score >= 0.7:
        initial_difficulty = 2
    else:
        initial_difficulty = 1

    first_exercise = next(
        (
            exercise
            for exercise in EXERCISES
            if exercise.difficulty == initial_difficulty
        ),
        None,
    )

    if first_exercise is None:
        first_exercise = select_exercise(
            current_difficulty=0,
        )

    if first_exercise is None:
        raise RuntimeError(
            "No hay ejercicios disponibles para iniciar la práctica."
        )

    state.phase = "practice"
    activate_exercise(state, first_exercise)

    # La práctica empieza después del mensaje de cierre del diagnóstico.
    state.practice_start = len(conversation) + 1

    state.teaching_strategy = "guided_explanation"
    state.next_step = (
        "Resolver el primer ejercicio de práctica "
        "con el nivel de apoyo correspondiente."
    )

    return profile_message(state.diagnostic_profile)


def _diagnostic_turn(
    client: Any,
    model_id: str,
    prompt: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
) -> str:
    if state.diagnostic_index >= len(DIAGNOSTIC_ITEMS):
        return _finish_diagnostic(state, conversation)

    item = set_diagnostic_item(
        state,
        state.diagnostic_index,
    )

    validation = _validate(prompt, state)

    evaluation = _evaluate_turn(
        client=client,
        model_id=model_id,
        conversation=conversation,
        state=state,
        prompt=prompt,
        current_question=item.statement,
        validation=validation,
    )

    resolved_validation = _resolve_validation(
        validation,
        evaluation,
        item.expected_value,
    )

    if not _has_observation(evaluation):
        return reask_message(
            evaluation.get("student_intent", "other")
        )

    update_pedagogical_state(
        state,
        evaluation,
        resolved_validation,
    )

    state.diagnostic_index += 1

    if state.diagnostic_index >= len(DIAGNOSTIC_ITEMS):
        return _finish_diagnostic(
            state,
            conversation,
        )

    next_item = get_diagnostic_item(
        state.diagnostic_index,
    )

    set_diagnostic_item(
        state,
        state.diagnostic_index,
    )

    return (
        acknowledgment(state.diagnostic_index - 1)
        + "\n\n"
        + next_item.statement
    )


# ---------------------------------------------------------------------------
# Historial del tutor
# ---------------------------------------------------------------------------

def _tutor_history(
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
) -> list[dict[str, Any]]:
    """
    Evita mezclar las preguntas del diagnóstico con el historial
    de práctica del estudiante.
    """
    if state.practice_start < 0:
        return conversation

    history = conversation[state.practice_start:]

    if history:
        return history

    if conversation:
        return [conversation[-1]]

    return []


# ---------------------------------------------------------------------------
# Práctica
# ---------------------------------------------------------------------------

def _practice_turn(
    client: Any,
    model_id: str,
    prompt: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
) -> str:
    if not state.active_exercise_statement:
        raise RuntimeError(
            "No existe un ejercicio activo en la fase de práctica."
        )

    current_exercise_id = state.active_exercise_id
    current_exercise_statement = state.active_exercise_statement

    validation = _validate(prompt, state)

    evaluation = _evaluate_turn(
        client=client,
        model_id=model_id,
        conversation=conversation,
        state=state,
        prompt=prompt,
        current_question=current_exercise_statement,
        validation=validation,
    )

    resolved_validation = _resolve_validation(
        validation,
        evaluation,
        state.expected_value,
    )

    # Actualizamos el estado antes de decidir qué ejercicio sigue.
    update_pedagogical_state(
        state,
        evaluation,
        resolved_validation,
    )

    # La transferencia se comprueba antes de activar otro ejercicio,
    # porque activate_exercise reinicia el indicador del ejercicio actual.
    verify_transfer(
        state,
        resolved_validation,
    )

    # Se registra el ejercicio resuelto antes de cambiarlo.
    if state.exercise_solved:
        record_exercise_result(state)

    # Si el motor decide continuar con práctica independiente,
    # se selecciona una actividad nueva.
    if (
        state.teaching_strategy == "independent_practice"
        and state.exercise_solved
    ):
        next_exercise = select_exercise_for_state(state)

        if next_exercise is not None:
            activate_exercise(
                state,
                next_exercise,
            )
        else:
            state.next_step = (
                "Se completó el banco de ejercicios disponible. "
                "Se requiere una nueva actividad para continuar."
            )

    # El tutor recibe el historial de práctica y el estado actualizado.
    history = _tutor_history(
        conversation,
        state,
    )

    response = generate_tutor_response(
        client=client,
        model_id=model_id,
        prompt=prompt,
        conversation=history,
        state=state,
    )

    # Si existe un ejercicio nuevo, comprobamos que el tutor lo haya
    # mencionado para que no quede activado silenciosamente.
    if (
        state.active_exercise_id != current_exercise_id
        and state.active_exercise_statement
        and state.active_exercise_statement not in response
    ):
        response = (
            response.rstrip()
            + "\n\n"
            + "Nuevo ejercicio:\n"
            + state.active_exercise_statement
        )

    return response


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------

def process_student_message(
    prompt: str,
    model_id: str,
    region: str,
    conversation: list[dict[str, Any]],
    pedagogical_state: PedagogicalState,
) -> str:
    """
    Procesa un mensaje del estudiante.

    Trabaja sobre copias temporales para evitar modificar la conversación
    o el estado original si ocurre un error.
    """
    if not prompt or not prompt.strip():
        raise ValueError("El mensaje del estudiante no puede estar vacío.")

    working_state = copy.deepcopy(pedagogical_state)
    working_conversation = copy.deepcopy(conversation)

    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
    )

    working_conversation.append({
        "role": "user",
        "content": [
            {"text": prompt},
        ],
    })

    try:
        if working_state.phase == "diagnostic":
            response = _diagnostic_turn(
                client=client,
                model_id=model_id,
                prompt=prompt,
                conversation=working_conversation,
                state=working_state,
            )

        elif working_state.phase == "practice":
            response = _practice_turn(
                client=client,
                model_id=model_id,
                prompt=prompt,
                conversation=working_conversation,
                state=working_state,
            )

        else:
            raise ValueError(
                f"Fase pedagógica desconocida: {working_state.phase}"
            )

        working_conversation.append({
            "role": "assistant",
            "content": [
                {"text": response},
            ],
        })

    except (RuntimeError, ValueError, TypeError):
        # Las copias temporales se descartan. El estado original
        # permanece intacto.
        raise

    # Solo confirmamos los cambios cuando el turno terminó correctamente.
    pedagogical_state.__dict__.update(
        copy.deepcopy(working_state.__dict__)
    )

    conversation.clear()
    conversation.extend(working_conversation)

    return response


# ---------------------------------------------------------------------------
# Interfaz de ejecución local
# ---------------------------------------------------------------------------

def run_converse(
    prompt: str,
    model_id: str,
    region: str,
    conversation: list[dict[str, Any]] | None = None,
    pedagogical_state: PedagogicalState | None = None,
) -> str:
    if conversation is None:
        conversation = []

    if pedagogical_state is None:
        pedagogical_state = PedagogicalState()

    return process_student_message(
        prompt=prompt,
        model_id=model_id,
        region=region,
        conversation=conversation,
        pedagogical_state=pedagogical_state,
    )


if __name__ == "__main__":
    import os

    model_id = os.getenv(
        "BEDROCK_MODEL_ID",
        "us.amazon.nova-pro-v1:0",
    )

    region = os.getenv(
        "AWS_REGION",
        "us-east-2",
    )

    conversation: list[dict[str, Any]] = []
    state = PedagogicalState()

    print("Kaanbal está listo. Escribe 'salir' para terminar.")
    print(intro_message())

    while True:
        try:
            prompt = input("\nTú: ").strip()

            if prompt.lower() in {"salir", "exit", "quit"}:
                print("Kaanbal: Hasta la próxima.")
                break

            response = run_converse(
                prompt=prompt,
                model_id=model_id,
                region=region,
                conversation=conversation,
                pedagogical_state=state,
            )

            print(f"\nKaanbal: {response}")

        except KeyboardInterrupt:
            print("\nKaanbal: Hasta la próxima.")
            break

        except Exception as exc:
            print(f"\nError: {exc}")
