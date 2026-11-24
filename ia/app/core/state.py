from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Estimate:
  """Estimación de una dimensión (procedural, conceptual, relacional)."""

  score: float = 0.5  # prior neutral: sin evidencia no sabemos nada
  confidence: float = 0.0  # qué tan respaldada está la estimación
  history: list[float] = field(default_factory=list)
  quotes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Hypothesis:
  """Hipótesis sobre una dificultad, con evidencia y ciclo de vida."""

  label: str
  kind: str = "difficulty"
  confidence: float = 0.3
  evidence: list[dict[str, Any]] = field(default_factory=list)
  status: str = "active"  # active | refuted


@dataclass
class PedagogicalState:
  concept: str = "linear_equations"
  phase: str = "diagnostic"  # diagnostic | practice
  diagnostic_index: int = 0
  practice_start: int = 0  # índice de conversation donde empieza la práctica

  procedural: Estimate = field(default_factory=Estimate)
  conceptual: Estimate = field(default_factory=Estimate)
  relational: Estimate = field(default_factory=Estimate)

  hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
  strategies_used: dict[str, int] = field(default_factory=dict)
  profile: dict[str, Any] = field(default_factory=dict)
  learning_evidence: list[dict[str, Any]] = field(default_factory=list)

  teaching_strategy: str = "diagnostic_question"
  scaffolding_level: int = 1
  hint_level: int = 0
  consecutive_failures: int = 0

  strategy_history: list[str] = field(default_factory=list)
  turn_count: int = 0
  attempt_count: int = 0
  transfer_verified: bool = False
  transfers_verified: int = 0
  exercise_solved: bool = False
  next_step: str = "Explorar conocimientos previos"
  expected_value: float | None = None
  active_exercise_id: str | None = None
  active_exercise_statement: str = ""
  exercise_difficulty: int = 0

  def estimates(self) -> dict[str, Estimate]:
    return {
        "procedural": self.procedural,
        "conceptual": self.conceptual,
        "relational": self.relational,
    }

  def min_confidence(self) -> float:
    return min(e.confidence for e in self.estimates().values())

  def as_prompt_context(self) -> dict[str, Any]:
    """Contexto compacto para los LLM (sin la respuesta esperada)."""
    return {
        "concept": self.concept,
        "phase": self.phase,
        "turn_count": self.turn_count,
        "attempt_count": self.attempt_count,
        "estimates": {
            name: {"score": est.score, "confidence": est.confidence}
            for name, est in self.estimates().items()
        },
        "hypotheses": [
            {
                "label": h.label,
                "confidence": round(h.confidence, 2),
                "evidence": [e["quote"] for e in h.evidence[-2:]],
            }
            for h in self.hypotheses.values()
            if h.status == "active"
        ],
        "teaching_strategy": self.teaching_strategy,
        "scaffolding_level": self.scaffolding_level,
        "hint_level": self.hint_level,
        "consecutive_failures": self.consecutive_failures,
        "exercise_solved": self.exercise_solved,
        "active_exercise_id": self.active_exercise_id,
        "active_exercise_statement": self.active_exercise_statement,
        "exercise_difficulty": self.exercise_difficulty,
        "next_step": self.next_step,
    }

  def debug_context(self) -> dict[str, Any]:
    """Todo el estado, para imprimirlo en la terminal."""
    return asdict(self)