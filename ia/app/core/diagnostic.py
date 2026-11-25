
from __future__ import annotations

from dataclasses import dataclass

from ia.app.core.state import PedagogicalState


@dataclass(frozen=True)
class DiagnosticItem:
    id: str
    statement: str
    expected_errors: tuple[str, ...]
    expected_value: float | None
    probes: tuple[str, ...]


DIAGNOSTIC_ITEMS: tuple[DiagnosticItem, ...] = (
    DiagnosticItem(
        id="d1",
        statement=(
            "Resuelve 3x = 15 y explícame cómo sabes "
            "que tu resultado es correcto."
        ),
        expected_errors=(
            "wrong_inverse_operation",
            "no_justification",
        ),
        expected_value=5,
        probes=(
            "¿Qué operación utilizaste?",
            "¿Cómo puedes comprobar el resultado?",
        ),
    ),
    DiagnosticItem(
        id="d2",
        statement=(
            "Resuelve 2x + 4 = 10. Explica los pasos que "
            "seguirías y por qué los haces en ese orden."
        ),
        expected_errors=(
            "order_of_steps_error",
            "operates_one_side_only",
            "sign_error",
        ),
        expected_value=3,
        probes=(
            "¿Qué necesitas hacer primero?",
            "¿Qué sucede con el 4?",
        ),
    ),
    DiagnosticItem(
        id="d3",
        statement=(
            "Un compañero afirma que, si 3x = 15, entonces "
            "x = 45. ¿Estás de acuerdo? Explica por qué."
        ),
        expected_errors=(
            "wrong_inverse_operation",
        ),
        expected_value=None,
        probes=(
            "¿Qué operación debería utilizar?",
            "¿Cómo comprobarías quién tiene razón?",
        ),
    ),
    DiagnosticItem(
        id="d4",
        statement=(
            "¿Qué significa para ti que dos expresiones sean "
            "iguales? Explícalo con un ejemplo propio."
        ),
        expected_errors=(
            "confuses_equality_meaning",
            "treats_x_as_label",
        ),
        expected_value=None,
        probes=(
            "¿Qué representa el signo igual?",
            "¿Cómo puedes demostrar que dos expresiones valen lo mismo?",
        ),
    ),
)


def intro_message() -> str:
    return (
        "Antes de comenzar a practicar, quiero conocer cómo razonas "
        "cuando resuelves ecuaciones. No importa si no sabes alguna "
        "respuesta; lo importante es entender cómo piensas."
    )


def get_diagnostic_item(index: int) -> DiagnosticItem:
    if index < 0 or index >= len(DIAGNOSTIC_ITEMS):
        raise IndexError("Índice de diagnóstico fuera de rango.")

    return DIAGNOSTIC_ITEMS[index]


def set_diagnostic_item(
    state: PedagogicalState,
    index: int,
) -> DiagnosticItem:
    item = get_diagnostic_item(index)

    state.diagnostic_index = index
    state.expected_value = item.expected_value
    state.next_step = item.statement

    return item


def acknowledgment(index: int) -> str:
    messages = (
        "Gracias. Ahora vamos a observar otro tipo de razonamiento.",
        "Bien, continuemos con una situación diferente.",
        "Gracias por explicar tu idea. Vamos con la siguiente.",
        "Ya casi terminamos esta primera parte.",
    )

    return messages[min(index, len(messages) - 1)]


def reask_message(
    student_intent: str,
) -> str:
    if student_intent == "expressing_confusion":
        return (
            "No pasa nada si todavía no tienes claro cómo resolverlo. "
            "Intenta explicarme qué parte te resulta difícil."
        )

    if student_intent in {
        "requesting_explanation",
        "requesting_hint",
    }:
        return (
            "Por ahora quiero conocer tu razonamiento inicial. "
            "Intenta decirme qué harías primero, aunque no estés seguro."
        )

    return (
        "Quiero conocer un poco más de tu razonamiento. "
        "¿Puedes explicarme cómo llegaste a esa idea?"
    )


def profile_message(profile: dict) -> str:
    strengths = profile.get("strengths", [])
    difficulties = profile.get("difficulties", [])

    labels = {
        "procedural": "procedimientos",
        "conceptual": "comprensión de los conceptos",
        "relational": "conexión entre ideas matemáticas",
    }

    if strengths:
        strengths_text = ", ".join(
            labels.get(item, item)
            for item in strengths
        )
        strength_message = (
            f"He observado indicios positivos en {strengths_text}. "
        )
    else:
        strength_message = (
            "Todavía necesito conocer mejor algunas de tus habilidades. "
        )

    if difficulties:
        difficulties_text = ", ".join(
            labels.get(item, item)
            for item in difficulties
        )
        difficulty_message = (
            f"Vamos a trabajar especialmente en {difficulties_text}. "
        )
    else:
        difficulty_message = (
            "Aún no hay suficiente evidencia para señalar dificultades "
            "específicas. "
        )

    return (
        "Terminamos la primera parte. "
        + strength_message
        + difficulty_message
        + "Ahora comenzaremos con ejercicios para seguir desarrollando "
        "tu comprensión."
    )
