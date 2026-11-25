
import re
from dataclasses import dataclass
from typing import Literal


# ---------------------------------------------------------
# Patrones numéricos
# ---------------------------------------------------------

_NUM = r"-?\d+(?:[.,]\d+)?(?:\s*/\s*-?\d+(?:[.,]\d+)?)?"

_N = r"-?\d+(?:[.,]\d+)?"

_X_VALUE = re.compile(
    rf"\bx\s*(?:=|vale|es(?:\s+igual\s+a)?)\s*({_NUM})",
    re.IGNORECASE,
)

_ONLY_NUMBER = re.compile(
    rf"^\s*({_NUM})\s*\.?\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------
# Detección de operaciones aritméticas
# ---------------------------------------------------------

_ARITHMETIC = re.compile(
    rf"(?<![\d.,])"
    rf"({_N})"
    rf"\s*"
    rf"(\*|×|x|/|÷|\+|-|\bpor\b|\bentre\b|\bmás\b|\bmenos\b)"
    rf"\s*"
    rf"({_N})"
    rf"\s*"
    rf"(?:=|es(?:\s+igual\s+a)?|da|son)"
    rf"\s*"
    rf"({_N})"
    rf"(?![\d.,])"
    rf"(?!\s*(?:\*|×|x|/|÷|\+|-)\s*\d)",
    re.IGNORECASE,
)


# ---------------------------------------------------------
# Estructura de validación
# ---------------------------------------------------------

@dataclass(frozen=True)
class AnswerValidation:
    status: Literal["correct", "incorrect", "unrecognized"]
    student_value: float | None
    expected_value: float


# ---------------------------------------------------------
# Conversión de números
# ---------------------------------------------------------

def _to_float(token: str) -> float | None:
    """
    Convierte un número o fracción a float.

    Ejemplos:
        "5"      -> 5.0
        "-2"     -> -2.0
        "0,5"    -> 0.5
        "15/3"   -> 5.0
        "1/0"    -> None
    """

    token = token.replace(",", ".").replace(" ", "")

    try:
        if "/" in token:
            numerator, denominator = token.split("/")

            denominator_value = float(denominator)

            if denominator_value == 0:
                return None

            return float(numerator) / denominator_value

        return float(token)

    except (ValueError, ZeroDivisionError):
        return None


def parse_number(text: str) -> float | None:
    """
    Convierte un texto numérico en float.

    Acepta:
        5
        -2
        0,5
        15/3

    Devuelve None si el texto no representa un número válido.
    """

    token = text.strip()

    if not re.fullmatch(_NUM, token):
        return None

    return _to_float(token)


# ---------------------------------------------------------
# Validación de respuesta final
# ---------------------------------------------------------

def validate_linear_answer(
    message: str,
    expected_value: float,
) -> AnswerValidation:
    """
    Compara la última respuesta final del estudiante con
    el valor esperado.

    Busca expresiones como:
        x = 5
        x vale 5
        x es 5
        x es igual a 5

    También acepta una respuesta que contenga únicamente
    un número.

    Si aparecen varias respuestas, utiliza la última.
    """

    text = message.lower()

    matches = _X_VALUE.findall(text)

    if not matches:
        only_number = _ONLY_NUMBER.match(text)

        matches = (
            [only_number.group(1)]
            if only_number
            else []
        )

    if not matches:
        return AnswerValidation(
            status="unrecognized",
            student_value=None,
            expected_value=expected_value,
        )

    student_value = _to_float(matches[-1])

    if student_value is None:
        return AnswerValidation(
            status="unrecognized",
            student_value=None,
            expected_value=expected_value,
        )

    status = (
        "correct"
        if abs(student_value - expected_value) < 1e-9
        else "incorrect"
    )

    return AnswerValidation(
        status=status,
        student_value=student_value,
        expected_value=expected_value,
    )


# ---------------------------------------------------------
# Detección de errores aritméticos
# ---------------------------------------------------------

def find_arithmetic_slips(message: str) -> list[str]:
    """
    Detecta operaciones aritméticas sencillas incorrectas.

    Ejemplos:
        "2 * 3 = 7"       -> detecta error
        "3 por 5 = 15"    -> no detecta error
        "10 - 4 = 8"      -> detecta error
        "12 entre 3 = 4"  -> no detecta error

    No pretende interpretar procedimientos algebraicos completos.
    """

    text = message.lower()

    slips: list[str] = []

    for match in _ARITHMETIC.finditer(text):

        # Evita interpretar una operación hipotética
        # introducida directamente por "si".
        prefix = text[:match.start()]

        if re.search(r"\bsi\s*$", prefix):
            continue

        left = parse_number(match.group(1))
        operator = match.group(2).lower()
        right = parse_number(match.group(3))
        claimed = parse_number(match.group(4))

        if (
            left is None
            or right is None
            or claimed is None
        ):
            continue

        if operator in ("*", "×", "x", "por"):
            result = left * right

        elif operator in ("/", "÷", "entre"):
            if right == 0:
                continue

            result = left / right

        elif operator in ("+", "más"):
            result = left + right

        else:
            result = left - right

        if abs(result - claimed) > 1e-6:
            slips.append(match.group(0).strip())

    return slips
