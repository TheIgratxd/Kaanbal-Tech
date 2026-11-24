from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ia.app.core.state import PedagogicalState


@dataclass(frozen=True)
class Exercise:
  id: str
  statement: str
  expected_value: float
  skill: str
  difficulty: int


EXERCISES = (
    Exercise("eq_001", "Resuelve: 3x = 15", 5, "linear_equations", 1),
    Exercise("eq_002", "Resuelve: 4x = 20", 5, "linear_equations", 1),
    Exercise("eq_003", "Resuelve: 2x + 4 = 10", 3, "linear_equations", 2),
    Exercise("eq_004", "Resuelve: 5x - 10 = 15", 5, "linear_equations", 2),
    Exercise("eq_005", "Resuelve: 3x + 6 = 21", 5, "linear_equations", 2),
    Exercise("eq_006", "Resuelve: 2x - 8 = 10", 9, "linear_equations", 3),
    Exercise("eq_007", "Resuelve: 4x + 7 = 23", 4, "linear_equations", 3),
    Exercise("eq_008", "Resuelve: 3x - 5 = 16", 7, "linear_equations", 3),
    Exercise("eq_009", "Resuelve: 2x + 9 = 25", 8, "linear_equations", 4),
    Exercise("eq_010", "Resuelve: 5x - 12 = 28", 8, "linear_equations", 4),
)


def select_exercise(
    current_exercise_id: str | None,
    current_difficulty: int,
    skill: str,
) -> Exercise:
  candidates = [
      exercise
      for exercise in EXERCISES
      if exercise.skill == skill and exercise.id != current_exercise_id
  ]
  if not candidates:
    raise ValueError(f"No hay ejercicios disponibles para {skill}.")

  harder = [
      exercise
      for exercise in candidates
      if exercise.difficulty == current_difficulty + 1
  ]
  if harder:
    return harder[0]

  same_or_higher = [
      exercise for exercise in candidates
      if exercise.difficulty >= current_difficulty
  ]
  return (same_or_higher or candidates)[0]


def activate_exercise(state: PedagogicalState, exercise: Exercise) -> None:
  state.active_exercise_id = exercise.id
  state.active_exercise_statement = exercise.statement
  state.exercise_difficulty = exercise.difficulty
  state.expected_value = exercise.expected_value
  state.concept = exercise.skill
  state.hint_level = 0
  state.consecutive_failures = 0
  state.transfer_verified = False
  state.exercise_solved = False