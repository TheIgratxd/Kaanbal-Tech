import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AnswerValidation:
  status: Literal["correct", "incorrect", "unrecognized"]
  student_value: float | None
  expected_value: float
  justification_detected: bool


def validate_linear_answer(
    message: str, expected_value: float
) -> AnswerValidation:
  normalized_message = message.lower()
  match = re.search(r"\bx\s*=\s*(-?\d+(?:\.\d+)?)", message.lower())
  justification_detected = any(
      marker in normalized_message
      for marker in (
          "porque",
          "por que",
          "ya que",
          "primero",
          "después",
          "despues",
          "dividí",
          "dividi",
          "multipliqué",
          "multiplique",
          "aislé",
          "aisle",
          "resté",
          "reste",
      )
  )
  if not match:
    return AnswerValidation(
        status="unrecognized",
        student_value=None,
        expected_value=expected_value,
        justification_detected=justification_detected,
    )

  student_value = float(match.group(1))
  status = (
      "correct"
      if abs(student_value - expected_value) < 1e-9
      else "incorrect"
  )
  return AnswerValidation(
      status=status,
      student_value=student_value,
      expected_value=expected_value,
      justification_detected=justification_detected,
  )
