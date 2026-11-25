
from __future__ import annotations

from typing import Any

from ia.app.core.state import Hypothesis, PedagogicalState


# ---------------------------------------------------------------------------
# Configuración pedagógica
# ---------------------------------------------------------------------------

STRATEGIES = {
    "diagnostic_question",
    "concrete_representation",
    "visual_representation",
    "guided_explanation",
    "independent_practice",
    "conceptual_challenge",
}

LEVEL_VALUE = {
    "not_observed": None,
    "none": 0.0,
    "weak": 0.25,
    "partial": 0.55,
    "strong": 0.9,
}

DIMENSIONS = ("procedural", "conceptual", "relational")

HYPOTHESIS_DIMENSION = {
    "wrong_inverse_operation": "procedural",
    "operates_one_side_only": "procedural",
    "sign_error": "procedural",
    "order_of_steps_error": "procedural",
    "rule_without_reason": "conceptual",
    "no_justification": "conceptual",
    "confuses_equality_meaning": "relational",
    "treats_x_as_label": "relational",
}

# Pedir ayuda no significa necesariamente tener dificultades.
# Estas intenciones modifican el apoyo, pero no reducen por sí solas
# las estimaciones de aprendizaje.
SUPPORT_REQUEST_INTENTS = {
    "requesting_hint",
    "requesting_explanation",
    "expressing_confusion",
}

NEXT_STEP = {
    "diagnostic_question": "Continuar explorando el razonamiento del estudiante.",
    "concrete_representation": "Representar el problema con elementos concretos.",
    "visual_representation": "Mostrar una representación visual del concepto.",
    "guided_explanation": "Acompañar al estudiante con una explicación guiada.",
    "independent_practice": "Proponer un ejercicio para resolver de manera independiente.",
    "conceptual_challenge": "Comprobar si el estudiante comprende por qué funciona el procedimiento.",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _validation_status(validation: dict[str, Any] | None) -> str:
    if not isinstance(validation, dict):
        return "unrecognized"

    status = validation.get("status")

    if status in {"correct", "incorrect", "unrecognized"}:
        return status

    # Compatibilidad con posibles nombres anteriores.
    if validation.get("is_correct") is True:
        return "correct"

    if validation.get("is_correct") is False:
        return "incorrect"

    return "unrecognized"


def _get_estimate(state: PedagogicalState, dimension: str) -> Any:
    return getattr(state, dimension)


def _observed_dimensions(evaluation: dict[str, Any]) -> dict[str, str]:
    dimensions = evaluation.get("dimensions", {})

    if not isinstance(dimensions, dict):
        return {}

    return {
        name: item.get("level", "not_observed")
        for name, item in dimensions.items()
        if name in DIMENSIONS
        and isinstance(item, dict)
        and item.get("level") in LEVEL_VALUE
        and item.get("level") != "not_observed"
    }


def _append_unique(items: list, value: Any) -> None:
    if value not in items:
        items.append(value)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def _get_min_confidence(state: PedagogicalState) -> float:
    try:
        return float(state.min_confidence())
    except (AttributeError, TypeError, ValueError):
        confidences = [
            float(_get_estimate(state, name).confidence)
            for name in DIMENSIONS
        ]
        return min(confidences) if confidences else 0.0


# ---------------------------------------------------------------------------
# Actualización de estimaciones
# ---------------------------------------------------------------------------

def update_estimate(
    estimate: Any,
    level: str,
    quote: str,
    hint_level: int = 0,
) -> None:
    """
    Actualiza una estimación únicamente cuando existe evidencia.

    El uso de pistas reduce el peso de la observación, pero no elimina
    la evidencia de aprendizaje.
    """
    if level not in LEVEL_VALUE:
        return

    value = LEVEL_VALUE[level]

    if value is None:
        return

    # Cuanto mayor sea el apoyo requerido, menor será el peso.
    hint_weight = {
        0: 1.0,
        1: 0.85,
        2: 0.7,
        3: 0.55,
        4: 0.4,
    }

    weight = hint_weight.get(
        max(0, min(int(hint_level), 4)),
        0.4,
    )

    old_score = float(estimate.score)

    # Actualización gradual para evitar que una sola respuesta
    # cambie drásticamente la estimación.
    estimate.score = (
        old_score * (1.0 - 0.25 * weight)
        + value * (0.25 * weight)
    )

    if not isinstance(estimate.history, list):
        estimate.history = []

    estimate.history.append({
        "level": level,
        "value": value,
        "weight": weight,
    })

    if not isinstance(estimate.quotes, list):
        estimate.quotes = []

    if quote:
        estimate.quotes.append(quote)

    # La confianza depende de la cantidad de observaciones,
    # no solamente de la puntuación obtenida.
    observations = len(estimate.history)

    estimate.confidence = min(
        0.95,
        0.18 + observations * 0.15,
    )


# ---------------------------------------------------------------------------
# Gestión de hipótesis pedagógicas
# ---------------------------------------------------------------------------

def update_hypotheses(
    state: PedagogicalState,
    evaluation: dict[str, Any],
) -> None:
    """
    Actualiza hipótesis sobre posibles dificultades.

    Una hipótesis representa una explicación provisional.
    No debe tratarse como una característica permanente del estudiante.
    """
    if not isinstance(state.hypotheses, list):
        state.hypotheses = []

    errors = evaluation.get("errors", [])

    if not isinstance(errors, list):
        errors = []

    for error in errors:
        if not isinstance(error, dict):
            continue

        label = error.get("label")
        quote = error.get("quote", "")

        dimension = HYPOTHESIS_DIMENSION.get(label)

        if dimension is None:
            continue

        existing = next(
            (
                hypothesis
                for hypothesis in state.hypotheses
                if hypothesis.label == label
            ),
            None,
        )

        if existing is None:
            existing = Hypothesis(
                label=label,
                kind=dimension,
                confidence=0.25,
                evidence=[quote] if quote else [],
                status="active",
            )

            state.hypotheses.append(existing)

        else:
            existing.confidence = min(
                0.95,
                existing.confidence + 0.15,
            )

            if quote and quote not in existing.evidence:
                existing.evidence.append(quote)

            existing.status = "active"

    # Evidencia positiva que puede debilitar hipótesis anteriores.
    dimensions = evaluation.get("dimensions", {})

    if not isinstance(dimensions, dict):
        return

    for hypothesis in state.hypotheses:
        dimension = getattr(hypothesis, "kind", None)
        observation = dimensions.get(dimension, {})

        if not isinstance(observation, dict):
            continue

        level = observation.get("level")

        if level not in {"partial", "strong"}:
            continue

        # La evidencia positiva reduce la confianza en una hipótesis,
        # pero no la elimina inmediatamente.
        hypothesis.confidence = max(
            0.0,
            hypothesis.confidence - (
                0.12 if level == "partial" else 0.2
            ),
        )

        if hypothesis.confidence < 0.15:
            hypothesis.status = "refuted"


# ---------------------------------------------------------------------------
# Evaluación del resultado
# ---------------------------------------------------------------------------

def judge_outcome(
    evaluation: dict[str, Any],
    validation: dict[str, Any] | None,
) -> str:
    """
    Clasifica el resultado del turno.

    Importante:
    - Una dimensión no observada no equivale a una dimensión deficiente.
    - Una respuesta correcta puede ser un buen resultado aunque todavía
      falte evidencia conceptual.
    """
    status = _validation_status(validation)

    errors = evaluation.get("errors", [])
    dimensions = _observed_dimensions(evaluation)

    if status == "incorrect":
        return "poor"

    if errors:
        return "poor"

    if any(
        level in {"none", "weak"}
        for level in dimensions.values()
    ):
        return "poor"

    if status == "correct":
        return "good"

    if dimensions and all(
        level in {"partial", "strong"}
        for level in dimensions.values()
    ):
        return "good"

    return "neutral"


# ---------------------------------------------------------------------------
# Gestión del nivel de apoyo
# ---------------------------------------------------------------------------

def update_support(
    state: PedagogicalState,
    outcome: str,
    student_intent: str,
) -> None:
    """
    Modifica el apoyo pedagógico sin confundir una solicitud de ayuda
    con un fracaso matemático.
    """
    state.consecutive_failures = max(
        0,
        int(state.consecutive_failures),
    )

    state.hint_level = max(
        0,
        min(4, int(state.hint_level)),
    )

    state.scaffolding_level = max(
        0,
        min(3, int(state.scaffolding_level)),
    )

    if outcome == "poor":
        state.consecutive_failures += 1
        state.hint_level = min(4, state.hint_level + 1)

        if state.consecutive_failures >= 2:
            state.scaffolding_level = min(
                3,
                state.scaffolding_level + 1,
            )

        return

    if outcome == "good":
        state.consecutive_failures = 0
        state.hint_level = max(0, state.hint_level - 1)

        if state.scaffolding_level > 0:
            state.scaffolding_level -= 1

        return

    # Solicitar una pista o explicación modifica el apoyo disponible,
    # pero no incrementa los fallos consecutivos.
    if student_intent in SUPPORT_REQUEST_INTENTS:
        state.hint_level = min(4, state.hint_level + 1)


# ---------------------------------------------------------------------------
# Selección de estrategia
# ---------------------------------------------------------------------------

def select_strategy(
    state: PedagogicalState,
    evaluation: dict[str, Any],
    validation: dict[str, Any] | None,
    outcome: str,
) -> str:
    """
    Selecciona la siguiente estrategia de enseñanza.

    En la fase de práctica no utiliza diagnostic_question:
    la exploración ya terminó y ahora se trabaja sobre dificultades
    específicas o comprensión conceptual.
    """
    if state.phase == "diagnostic":
        return "diagnostic_question"

    intent = evaluation.get("student_intent", "other")
    status = _validation_status(validation)

    dimensions = _observed_dimensions(evaluation)

    procedural = dimensions.get("procedural")
    conceptual = dimensions.get("conceptual")
    relational = dimensions.get("relational")

    # La petición explícita de ayuda tiene prioridad.
    if intent in SUPPORT_REQUEST_INTENTS:
        if state.scaffolding_level >= 2:
            return "concrete_representation"

        return "guided_explanation"

    # Si el estudiante tuvo dificultades, se proporciona apoyo.
    if outcome == "poor":
        if state.scaffolding_level >= 2:
            return "concrete_representation"

        if state.scaffolding_level == 1:
            return "visual_representation"

        return "guided_explanation"

    # Una respuesta correcta no implica que ya exista comprensión
    # conceptual. Se puede comprobar con un reto breve.
    if status == "correct":
        if conceptual not in {"partial", "strong"}:
            return "conceptual_challenge"

        if relational not in {"partial", "strong"}:
            return "conceptual_challenge"

        return "independent_practice"

    # Cuando el estudiante analiza o corrige razonamientos,
    # conviene comprobar que puede justificar su interpretación.
    if intent in {
        "evaluating_reasoning",
        "correcting_own_reasoning",
        "checking_answer",
        "providing_example",
    }:
        return "conceptual_challenge"

    # Si el procedimiento es correcto, pero no hay suficiente
    # evidencia conceptual, se propone una comprobación.
    if procedural in {"partial", "strong"}:
        if conceptual not in {"partial", "strong"}:
            return "conceptual_challenge"

        return "independent_practice"

    # Si la confianza general sigue siendo baja, se usa una
    # actividad guiada y específica, no se reinicia el diagnóstico.
    if _get_min_confidence(state) < 0.25:
        return "guided_explanation"

    return "conceptual_challenge"


# ---------------------------------------------------------------------------
# Evidencia de aprendizaje
# ---------------------------------------------------------------------------

def record_learning_evidence(
    state: PedagogicalState,
    evaluation: dict[str, Any],
    validation: dict[str, Any] | None,
    outcome: str,
) -> None:
    if not isinstance(state.learning_evidence, list):
        state.learning_evidence = []

    dimensions = evaluation.get("dimensions", {})

    if not isinstance(dimensions, dict):
        dimensions = {}

    observed = {}

    for name in DIMENSIONS:
        item = dimensions.get(name, {})

        if not isinstance(item, dict):
            continue

        level = item.get("level", "not_observed")

        if level != "not_observed":
            observed[name] = {
                "level": level,
                "quote": item.get("quote", ""),
            }

    evidence = {
        "turn": state.turn_count,
        "intent": evaluation.get("student_intent", "other"),
        "dimensions": observed,
        "validation": _validation_status(validation),
        "outcome": outcome,
        "errors": [
            error.get("label")
            for error in evaluation.get("errors", [])
            if isinstance(error, dict)
        ],
    }

    state.learning_evidence.append(evidence)


# ---------------------------------------------------------------------------
# Perfil del estudiante
# ---------------------------------------------------------------------------

def build_profile(state: PedagogicalState) -> dict[str, Any]:
    """
    Construye un perfil basado en las estimaciones actuales.

    Este perfil puede actualizarse durante la práctica.
    No representa un diagnóstico definitivo ni una etiqueta permanente.
    """
    strengths = []
    difficulties = []
    observations = {}

    for dimension in DIMENSIONS:
        estimate = _get_estimate(state, dimension)

        score = float(estimate.score)
        confidence = float(estimate.confidence)

        observations[dimension] = {
            "score": round(score, 3),
            "confidence": round(confidence, 3),
        }

        # Se necesita cierta cantidad de evidencia para afirmar
        # que existe una fortaleza o una dificultad.
        if confidence < 0.3:
            continue

        if score >= 0.6:
            strengths.append(dimension)

        elif score <= 0.4:
            difficulties.append(dimension)

    active_hypotheses = [
        {
            "label": hypothesis.label,
            "dimension": hypothesis.kind,
            "confidence": round(
                float(hypothesis.confidence),
                3,
            ),
        }
        for hypothesis in state.hypotheses
        if hypothesis.status == "active"
        and hypothesis.confidence >= 0.3
    ]

    overall_confidence = _mean([
        observations[name]["confidence"]
        for name in DIMENSIONS
    ])

    return {
        "strengths": strengths,
        "difficulties": difficulties,
        "hypotheses": active_hypotheses,
        "observations": observations,
        "overall_confidence": round(
            overall_confidence,
            3,
        ),
    }


# ---------------------------------------------------------------------------
# Actualización integral del estado
# ---------------------------------------------------------------------------

def update_pedagogical_state(
    state: PedagogicalState,
    evaluation: dict[str, Any],
    validation: dict[str, Any] | None,
) -> PedagogicalState:
    """
    Actualiza el estado pedagógico a partir de una evaluación.

    Orden:
    1. Registrar el turno.
    2. Actualizar estimaciones.
    3. Actualizar hipótesis.
    4. Determinar el resultado.
    5. Actualizar el apoyo.
    6. Seleccionar estrategia.
    7. Actualizar perfil y siguiente paso.
    """
    state.turn_count += 1

    status = _validation_status(validation)

    if status in {"correct", "incorrect"}:
        state.attempt_count += 1

    # Una respuesta correcta resuelve el ejercicio activo.
    # El gestor de ejercicios podrá registrar el historial antes
    # de activar el siguiente ejercicio.
    if state.phase == "practice":
        state.exercise_solved = status == "correct"

    dimensions = evaluation.get("dimensions", {})

    if not isinstance(dimensions, dict):
        dimensions = {}

    for name in DIMENSIONS:
        item = dimensions.get(name, {})

        if not isinstance(item, dict):
            continue

        update_estimate(
            estimate=_get_estimate(state, name),
            level=item.get("level", "not_observed"),
            quote=item.get("quote", ""),
            hint_level=state.hint_level,
        )

    update_hypotheses(state, evaluation)

    outcome = judge_outcome(
        evaluation,
        validation,
    )

    record_learning_evidence(
        state,
        evaluation,
        validation,
        outcome,
    )

    state.strategies_used = (
        state.strategies_used
        if isinstance(state.strategies_used, list)
        else []
    )

    if state.phase == "diagnostic":
        state.teaching_strategy = "diagnostic_question"
        state.next_step = NEXT_STEP["diagnostic_question"]

        state.profile = build_profile(state)

        return state

    update_support(
        state,
        outcome,
        evaluation.get("student_intent", "other"),
    )

    strategy = select_strategy(
        state,
        evaluation,
        validation,
        outcome,
    )

    state.teaching_strategy = strategy
    state.next_step = NEXT_STEP[strategy]

    _append_unique(
        state.strategies_used,
        strategy,
    )

    if not isinstance(state.strategy_history, list):
        state.strategy_history = []

    state.strategy_history.append({
        "turn": state.turn_count,
        "strategy": strategy,
        "outcome": outcome,
        "intent": evaluation.get("student_intent", "other"),
    })

    # El perfil se actualiza después de cada turno de práctica.
    state.profile = build_profile(state)

    return state


# ---------------------------------------------------------------------------
# Verificación de transferencia
# ---------------------------------------------------------------------------

def verify_transfer(
    state: PedagogicalState,
    validation: dict[str, Any] | None,
) -> bool:
    """
    Registra evidencia de transferencia cuando el estudiante resuelve
    un ejercicio de dificultad igual o superior a 2.

    No basta con acertar: también se requiere evidencia conceptual
    y un nivel de ayuda reducido.
    """
    state.transfer_verified = False

    if state.phase != "practice":
        return False

    if _validation_status(validation) != "correct":
        return False

    if state.exercise_difficulty < 2:
        return False

    if state.conceptual.score < 0.55:
        return False

    if state.conceptual.confidence < 0.3:
        return False

    if state.hint_level > 1:
        return False

    state.transfer_verified = True
    state.transfers_verified += 1

    return True
