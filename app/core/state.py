from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PedagogicalState:
  concept: str = "linear_equations"

  conceptual_mastery: float = 0.0
  procedural_mastery: float = 0.0
  relational_mastery: float = 0.0

  confidence: float = 0.0
  misconception_hypotheses: list[str] = field(default_factory=list)
  learning_evidence: list[dict[str, Any]] = field(default_factory=list)

  teaching_strategy: str = "diagnostic_question"
  scaffolding_level: int = 1
  hint_level: int = 0

  strategy_history: list[str] = field(default_factory=list)
  turn_count: int = 0
  attempt_count: int = 0
  transfer_verified: bool = False
  next_step: str = "Explore prior knowledge"
  expected_value: float | None = None
  active_exercise_id: str | None = None
  active_exercise_statement: str = ""
  exercise_difficulty: int = 0

  def as_prompt_context(self) -> dict[str, Any]:
    context = asdict(self)
    context.pop("expected_value", None)
    return context
