
from __future__ import annotations

from dataclasses import dataclass

from ia.app.core.state import PedagogicalState


@dataclass(frozen=True)
class Exercise:
    id: str
    statement: str
    expected_value: float
    skill: str
    difficulty: int


EXERCISES: tuple[Exercise, ...] = (
    Exercise(
        id="eq_001",
        statement="Resuelve la ecuación: 3x = 15",
        expected_value=5,
        skill="inverse_operation",
        difficulty=1,
    ),
    Exercise(
        id="eq_002",
        statement="Resuelve la ecuación: x + 7 = 12",
        expected_value=5,
        skill="inverse_operation",
        difficulty=1,
    ),
    Exercise(
        id="eq_003",
        statement="Resuelve la ecuación: 2x + 4 = 10",
        expected_value=3,
        skill="equivalent_transformations",
        difficulty=2,
    ),
    Exercise(
        id="eq_004",
        statement="Resuelve la ecuación: 5x - 8 = 17",
        expected_value=5,
        skill="equivalent_transformations",
        difficulty=2,
    ),
    Exercise(
        id="eq_005",
        statement="Resuelve la ecuación: 4x + 6 = 30",
        expected_value=6,
        skill="equivalent_transformations",
        difficulty=2,
    ),
    Exercise(
        id="eq_006",
        statement="Resuelve la ecuación: 3(x + 2) = 21",
        expected_value=5,
        skill="distributive_property",
        difficulty=3,
    ),
    Exercise(
        id="eq_007",
        statement="Resuelve la ecuación: 2(x - 3) + 4 = 12",
        expected_value=7,
        skill="distributive_property",
        difficulty=3,
    ),
    Exercise(
        id="eq_008",
        statement="Resuelve la ecuación: 5x + 3 = 2x + 18",
        expected_value=5,
        skill="variables_both_sides",
        difficulty=3,
    ),
    Exercise(
        id="eq_009",
        statement="Resuelve la ecuación: 4(x + 2) = 2x + 18",
        expected_value=5,
        skill="variables_both_sides",
        difficulty=4,
    ),
    Exercise(
        id="eq_010",
        statement="Resuelve la ecuación: 3(2x - 1) = 4x + 9",
        expected_value=6,
        skill="variables_both_sides",
        difficulty=4,
    ),
)


def select_exercise(
    current_exercise_id: str | None = None,
    current_difficulty: int = 1,
    skill: str | None = None,
    excluded_ids: set[str] | None = None,
) -> Exercise | None:
    """
    Selecciona un ejercicio no presentado anteriormente.

    Prioridad:
    1. Evitar el ejercicio actual y los ya presentados.
    2. Buscar la dificultad inmediatamente superior.
    3. Buscar otro ejercicio de dificultad igual o superior.
    4. Si no existe, buscar cualquier ejercicio disponible.
    """
    excluded = set(excluded_ids or set())

    if current_exercise_id:
        excluded.add(current_exercise_id)

    candidates = [
        exercise
        for exercise in EXERCISES
        if exercise.id not in excluded
    ]

    if not candidates:
        return None

    if skill:
        skill_candidates = [
            exercise
            for exercise in candidates
            if exercise.skill == skill
        ]

        if skill_candidates:
            candidates = skill_candidates

    target_difficulty = current_difficulty + 1

    exact_level = [
        exercise
        for exercise in candidates
        if exercise.difficulty == target_difficulty
    ]

    if exact_level:
        return exact_level[0]

    higher_level = [
        exercise
        for exercise in candidates
        if exercise.difficulty > current_difficulty
    ]

    if higher_level:
        return min(
            higher_level,
            key=lambda exercise: exercise.difficulty,
        )

    same_level = [
        exercise
        for exercise in candidates
        if exercise.difficulty == current_difficulty
    ]

    if same_level:
        return same_level[0]

    return candidates[0]


def select_exercise_for_state(
    state: PedagogicalState,
) -> Exercise | None:
    excluded = set(state.presented_exercises)

    return select_exercise(
        current_exercise_id=state.active_exercise_id,
        current_difficulty=state.exercise_difficulty,
        excluded_ids=excluded,
    )


def activate_exercise(
    state: PedagogicalState,
    exercise: Exercise,
) -> None:
    """
    Activa una actividad nueva.

    Los resultados anteriores permanecen en completed_exercises.
    Los indicadores del ejercicio actual se reinician.
    """
    state.active_exercise_id = exercise.id
    state.active_exercise_statement = exercise.statement
    state.expected_value = exercise.expected_value
    state.exercise_difficulty = exercise.difficulty
    state.concept = "ecuaciones lineales"

    if exercise.id not in state.presented_exercises:
        state.presented_exercises.append(exercise.id)

    state.exercise_solved = False
    state.transfer_verified = False

    state.hint_level = 0
    state.consecutive_failures = 0


def record_exercise_result(
    state: PedagogicalState,
) -> None:
    """
    Guarda el resultado del ejercicio activo antes de cambiarlo.
    No duplica registros si la función se ejecuta dos veces.
    """
    if not state.exercise_solved:
        return

    exercise_id = state.active_exercise_id

    if not exercise_id:
        return

    already_recorded = any(
        item.get("id") == exercise_id
        for item in state.completed_exercises
    )

    if already_recorded:
        return

    state.completed_exercises.append({
        "id": exercise_id,
        "statement": state.active_exercise_statement,
        "difficulty": state.exercise_difficulty,
        "expected_value": state.expected_value,
        "transfer_verified": state.transfer_verified,
        "turn": state.turn_count,
    })

    state.last_exercise_solved = True
