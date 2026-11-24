import re
from dataclasses import dataclass
from typing import Literal

_NUM = r"-?\d+(?:[.,]\d+)?(?:\s*/\s*-?\d+)?"
_X_VALUE = re.compile(rf"\bx\s*(?:=|vale|es|son)\s*({_NUM})")
_ONLY_NUMBER = re.compile(rf"^\s*({_NUM})\s*\.?\s*$")
_N = r"\d+(?:[.,]\d+)?"
_ARITHMETIC = re.compile(
    rf"(?<![\d.,])({_N})\s*([*×x/÷+\-])\s*({_N})\s*(?:=|es|da|son)\s*({_N})"
    r"(?![.,]?\d)(?!\s*[*×x/÷+\-]\s*\d)"
)


@dataclass(frozen=True)
class AnswerValidation:
  status: Literal["correct", "incorrect", "unrecognized"]
  student_value: float | None
  expected_value: float


def _to_float(token: str) -> float | None:
  token = token.replace(",", ".").replace(" ", "")
  try:
    if "/" in token:
      numerator, denominator = token.split("/")
      if float(denominator) == 0:
        return None
      return float(numerator) / float(denominator)
    return float(token)
  except ValueError:
    return None


def parse_number(text: str) -> float | None:
  """Convierte '5', '-2', '0,5' o '15/3' en float; None si no es un número."""
  token = text.strip()
  if not re.fullmatch(_NUM, token):
    return None
  return _to_float(token)


def validate_linear_answer(
    message: str, expected_value: float
) -> AnswerValidation:
  """Compara la ÚLTIMA respuesta final del estudiante con la esperada.

  Se usa la última coincidencia porque en "x = 15/3, x = 5" la respuesta
  final es la última, no la primera.
  """
  text = message.lower()
  matches = _X_VALUE.findall(text)
  if not matches:
    only_number = _ONLY_NUMBER.match(text)
    matches = [only_number.group(1)] if only_number else []
  if not matches:
    return AnswerValidation("unrecognized", None, expected_value)

  student_value = _to_float(matches[-1])
  if student_value is None:
    return AnswerValidation("unrecognized", None, expected_value)
  status = (
      "correct"
      if abs(student_value - expected_value) < 1e-9
      else "incorrect"
  )
  return AnswerValidation(status, student_value, expected_value)


def find_arithmetic_slips(message: str) -> list[str]:
  """Detecta cuentas simples mal hechas ("2*3 = 7") sin usar el LLM.

  Ignora afirmaciones condicionales ("si 3 * 45 es 15") y cadenas más largas
  ("5 * 3 = 3 * 5"), donde el patrón simple no aplica.
  """
  text = message.lower()
  slips = []
  for match in _ARITHMETIC.finditer(text):
    if re.search(r"\bsi\s*$", text[: match.start()]):
      continue
    left = parse_number(match.group(1))
    right = parse_number(match.group(3))
    claimed = parse_number(match.group(4))
    if left is None or right is None or claimed is None:
      continue
    operator = match.group(2)
    if operator in "*×x":
      result = left * right
    elif operator in "/÷":
      if right == 0:
        continue
      result = left / right
    elif operator == "+":
      result = left + right
    else:
      result = left - right
    if abs(result - claimed) > 1e-6:
      slips.append(match.group(0).strip())
  return slips