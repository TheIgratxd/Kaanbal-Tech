
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Estimate:
    score: float = 0.5
    confidence: float = 0.0
    history: list[dict[str, Any]] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)


@dataclass
class Hypothesis:
    label: str
    kind: str
    confidence: float = 0.25
    evidence: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class PedagogicalState:
    # Identificación del contenido
    concept: str = "ecuaciones lineales"

    # Fase del proceso
    phase: str = "diagnostic"
    diagnostic_index: int = 0
    practice_start: int = 0

    # Estimaciones de aprendizaje
    procedural: Estimate = field(default_factory=Estimate)
    conceptual: Estimate = field(default_factory=Estimate)
    relational: Estimate = field(default_factory=Estimate)

    # Hipótesis y perfiles
    hypotheses: list[Hypothesis] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    diagnostic_profile: dict[str, Any] = field(default_factory=dict)

    # Evidencia de aprendizaje
    learning_evidence: list[dict[str, Any]] = field(default_factory=list)

    # Estrategia pedagógica
    teaching_strategy: str = "diagnostic_question"
    scaffolding_level: int = 0
    hint_level: int = 0
    consecutive_failures: int = 0

    strategies_used: list[str] = field(default_factory=list)
    strategy_history: list[dict[str, Any]] = field(default_factory=list)

    # Contadores
    turn_count: int = 0
    attempt_count: int = 0

    # Transferencia de aprendizaje
    transfer_verified: bool = False
    transfers_verified: int = 0

    # Ejercicio activo
    exercise_solved: bool = False
    last_exercise_solved: bool = False
    next_step: str = ""

    expected_value: float | None = None
    active_exercise_id: str | None = None
    active_exercise_statement: str = ""
    exercise_difficulty: int = 1

    # Historial de ejercicios
    presented_exercises: list[str] = field(default_factory=list)
    completed_exercises: list[dict[str, Any]] = field(default_factory=list)

    def estimates(self) -> dict[str, Estimate]:
        return {
            "procedural": self.procedural,
            "conceptual": self.conceptual,
            "relational": self.relational,
        }

    def min_confidence(self) -> float:
        values = [
            estimate.confidence
            for estimate in self.estimates().values()
        ]

        return min(values) if values else 0.0

    def as_prompt_context(self) -> dict[str, Any]:
        """
        Devuelve únicamente información útil para el modelo tutor.
        No es necesario enviar todo el historial interno.
        """
        active_hypotheses = [
            asdict(hypothesis)
            for hypothesis in self.hypotheses
            if hypothesis.status == "active"
        ]

        return {
            "concept": self.concept,
            "phase": self.phase,
            "estimates": {
                name: asdict(estimate)
                for name, estimate in self.estimates().items()
            },
            "profile": self.profile,
            "active_hypotheses": active_hypotheses,
            "teaching_strategy": self.teaching_strategy,
            "scaffolding_level": self.scaffolding_level,
            "hint_level": self.hint_level,
            "consecutive_failures": self.consecutive_failures,
            "active_exercise": {
                "id": self.active_exercise_id,
                "statement": self.active_exercise_statement,
                "difficulty": self.exercise_difficulty,
            },
            "exercise_solved": self.exercise_solved,
            "completed_exercises": self.completed_exercises,
            "next_step": self.next_step,
        }

    def debug_context(self) -> dict[str, Any]:
        return asdict(self)
