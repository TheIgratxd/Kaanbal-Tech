import json
import re
from dataclasses import asdict
from typing import Any

from botocore.exceptions import ClientError

from ia.app.core.answer_validator import (
    find_arithmetic_slips,
    parse_number,
    validate_linear_answer,
)

from ia.app.core.state import PedagogicalState


# ---------------------------------------------------------------------------
# Contrato de evaluación
# ---------------------------------------------------------------------------

DIMENSIONS = ("procedural", "conceptual", "relational")

VALID_LEVELS = {
    "not_observed",
    "none",
    "weak",
    "partial",
    "strong",
}

VALID_INTENTS = {
    "asking_question",
    "requesting_hint",
    "requesting_explanation",
    "expressing_confusion",
    "giving_answer",
    "showing_procedure",
    "evaluating_reasoning",
    "correcting_own_reasoning",
    "checking_answer",
    "providing_example",
    "requesting_practice",
    "confirming_understanding",
    "other",
}

ERROR_LABELS = {
    "operates_one_side_only",
    "wrong_inverse_operation",
    "sign_error",
    "treats_x_as_label",
    "no_justification",
    "confuses_equality_meaning",
    "order_of_steps_error",
    "rule_without_reason",
}

STRATEGY_LABELS = {
    "inverse_operation",
    "guess_and_check",
    "balance_both_sides",
    "undo_steps",
    "pattern_or_memory",
    "substitution_check",
    "equivalent_transformations",
    "other",
}

JSON_REMINDER = (
    "\n\nRECUERDA: responde únicamente con el objeto JSON solicitado. "
    "No agregues explicaciones ni texto fuera del JSON."
)


# ---------------------------------------------------------------------------
# Instrucciones del evaluador
# ---------------------------------------------------------------------------


EVALUATOR_PROMPT = """
Eres un evaluador pedagógico de matemáticas para estudiantes de
15 años en adelante.

Tu función es OBSERVAR y REPORTAR evidencia del razonamiento
del estudiante.

No converses con él, no enseñes, no resuelvas ejercicios
y no felicites.

Analiza exclusivamente el último mensaje del estudiante.
El historial y el estado pedagógico son contexto para interpretar
el mensaje, pero no son evidencia nueva del estudiante.

Los estudiantes pueden escribir informalmente. Interpreta su
intención, pero todas las citas deben copiarse literalmente.

Devuelve únicamente JSON válido con esta estructura:

{
    "student_intent": "INTENCION",
    "intent_quote": "cita literal",
    "final_answer": {
        "value": "número como texto o null",
        "quote": "cita literal donde aparece el resultado"
    },
    "dimensions": {
        "procedural": {
            "level": "not_observed|none|weak|partial|strong",
            "quote": "cita literal"
        },
        "conceptual": {
            "level": "not_observed|none|weak|partial|strong",
            "quote": "cita literal"
        },
        "relational": {
            "level": "not_observed|none|weak|partial|strong",
            "quote": "cita literal"
        }
    },
    "errors": [
        {
            "label": "ETIQUETA_PERMITIDA",
            "quote": "cita literal"
        }
    ],
    "strategies_used": ["ESTRATEGIA_PERMITIDA"]
}

--------------------------------------------------
1. INTENCIONES PERMITIDAS
--------------------------------------------------

- asking_question:
  Formula una pregunta, pero no necesariamente solicita ayuda.

- requesting_hint:
  Pide una pista o indicación breve para continuar.

- requesting_explanation:
  Solicita que se le explique un concepto o procedimiento.

- expressing_confusion:
  Expresa que no entiende, no sabe cómo continuar o está confundido.

- giving_answer:
  Proporciona un resultado sin desarrollar necesariamente
  el procedimiento.

- showing_procedure:
  Explica operaciones o pasos que realizó o realizaría.

- evaluating_reasoning:
  Analiza, cuestiona o evalúa el razonamiento de otra persona.

- correcting_own_reasoning:
  Reconoce y corrige un error de su propio razonamiento.

- checking_answer:
  Comprueba un resultado o pregunta si su respuesta es correcta.

- providing_example:
  Propone un ejemplo propio para explicar una idea.

- requesting_practice:
  Solicita otro ejercicio o más práctica.

- confirming_understanding:
  Afirma que comprendió una explicación o procedimiento.

- other:
  El mensaje no corresponde claramente a las categorías anteriores.

Si hay varias intenciones, selecciona la principal del mensaje.

No confundas una pregunta conceptual con una solicitud de ayuda.

--------------------------------------------------
2. EVALUACIÓN DE LAS DIMENSIONES
--------------------------------------------------

Evalúa cada dimensión de forma independiente.

A) PROCEDURAL

Evalúa si las operaciones, transformaciones y pasos matemáticos
realizados son correctos y coherentes con el ejercicio.

- strong:
  Procedimiento correcto y suficientemente desarrollado.

- partial:
  Procedimiento mayormente correcto, pero incompleto o con pasos
  que todavía no permiten confirmar todo el razonamiento.

- weak:
  Muestra un intento con errores relevantes, pero también
  evidencia parcial de cómo abordar el procedimiento.

- none:
  Existe evidencia explícita de que no sabe realizar el
  procedimiento o desarrolla uno completamente incorrecto.

- not_observed:
  No hay evidencia suficiente sobre el procedimiento.

Si únicamente proporciona el resultado final, el nivel máximo
es partial.

No inventes pasos que el estudiante no haya escrito.

B) CONCEPTUAL

Evalúa si comprende por qué funcionan las operaciones y
los procedimientos matemáticos.

- strong:
  Explica correctamente el principio matemático y lo aplica.

- partial:
  Explica una idea correcta, pero de manera incompleta.

- weak:
  Utiliza una regla de memoria sin explicar su fundamento,
  o muestra una comprensión parcial con alguna confusión.

- none:
  Presenta una concepción matemática explícitamente incorrecta
  o expresa desconocimiento del concepto evaluado.

- not_observed:
  No hay evidencia conceptual suficiente.

No confundas una explicación extensa con comprensión conceptual.
La explicación debe ser matemáticamente válida.

C) RELATIONAL

Evalúa si conecta ideas matemáticas, interpreta la igualdad,
comprueba resultados, propone ejemplos o analiza razonamientos.

- strong:
  Establece conexiones correctas y las justifica.

- partial:
  Establece una conexión correcta, pero poco desarrollada.

- weak:
  Intenta establecer una relación, pero la confunde o la aplica
  incorrectamente.

- none:
  Existe evidencia explícita de una interpretación incorrecta
  de las relaciones matemáticas.

- not_observed:
  No hay evidencia relacional suficiente.

IMPORTANTE:
Una comprobación solo es válida si utiliza el ejercicio original
y el resultado que se está comprobando.

Una operación aritmética correcta no necesariamente constituye
una comprobación válida del ejercicio.

--------------------------------------------------
3. VALIDACIÓN MATEMÁTICA DETERMINISTA
--------------------------------------------------

Recibirás información adicional con el resultado de un validador
matemático basado en código.

Esta información tiene la siguiente estructura:

{
    "status": "correct|incorrect|unrecognized",
    "student_value": 5,
    "expected_value": 3
}

REGLAS OBLIGATORIAS:

1. Si status es "incorrect", el resultado final del estudiante
   es matemáticamente incorrecto.

2. Si status es "correct", el resultado final coincide con
   el valor esperado.

3. Si status es "unrecognized", no puedes afirmar que el resultado
   sea correcto o incorrecto basándote únicamente en esa validación.

4. Nunca contradigas la validación determinista.

5. La validación del resultado no demuestra que el procedimiento
   sea correcto.

6. Una respuesta final incorrecta no implica automáticamente
   que las tres dimensiones sean débiles o nulas.

7. Evalúa el procedimiento escrito por el estudiante,
   independientemente de que su resultado final sea correcto.

8. Si el estudiante obtiene un resultado incorrecto mediante
   un procedimiento correcto, considera si existe un error
   aritmético antes de evaluar su comprensión conceptual.

9. Si el estudiante obtiene el resultado correcto mediante
   un procedimiento incorrecto, no marques el procedimiento
   como strong.

10. Si el resultado no puede identificarse en el mensaje,
    utiliza null en final_answer.value.

La validación determinista es la autoridad para determinar
la coincidencia del resultado final, no para evaluar por sí sola
la comprensión del estudiante.

--------------------------------------------------
4. RESPUESTA FINAL
--------------------------------------------------

Identifica el resultado que el estudiante presenta como
respuesta propia al ejercicio actual.

No extraigas como respuesta propia:

- El resultado de un compañero.
- Un número mencionado en un ejemplo hipotético.
- Una operación que el estudiante está cuestionando.
- Un resultado que aparece únicamente en una pregunta.
- El resultado esperado proporcionado por el validador.

Si el estudiante proporciona un resultado propio identificable,
inclúyelo como texto en final_answer.value.

Si no hay resultado propio identificable, utiliza null.

La respuesta final debe representar lo que escribió el estudiante,
no lo que debería haber obtenido.

--------------------------------------------------
5. ERRORES PERMITIDOS
--------------------------------------------------

Utiliza exclusivamente las siguientes etiquetas:

- operates_one_side_only
- wrong_inverse_operation
- sign_error
- treats_x_as_label
- no_justification
- confuses_equality_meaning
- order_of_steps_error
- rule_without_reason

Definiciones:

- operates_one_side_only:
  Modifica únicamente un lado de una igualdad cuando debía
  conservar la equivalencia entre ambos lados.

- wrong_inverse_operation:
  Aplica una operación inversa incorrecta para despejar
  una variable.

- sign_error:
  Cambia o utiliza incorrectamente un signo.

- treats_x_as_label:
  Interpreta la variable como una etiqueta o un símbolo
  sin significado numérico.

- no_justification:
  Presenta una afirmación matemática sin justificación cuando
  el ejercicio solicita explícitamente explicar el razonamiento.

- confuses_equality_meaning:
  Interpreta incorrectamente el significado de la igualdad.

- order_of_steps_error:
  Ejecuta pasos en un orden que no conserva la equivalencia
  o que impide resolver correctamente el ejercicio.

- rule_without_reason:
  Utiliza una regla de memoria sin explicar por qué funciona.

REGLAS:

- Un error solo se registra cuando el estudiante lo comete
  en su propio razonamiento.

- Si el estudiante detecta o describe un error de un compañero,
  NO registres ese error como propio.

- No registres errores aritméticos: otro componente los comprueba
  mediante código.

- No registres errores por ausencia de información.

- No inventes errores que no estén respaldados por una cita literal.

- Puedes registrar más de un error si existen evidencias
  independientes para cada uno.

--------------------------------------------------
6. ESTRATEGIAS PERMITIDAS
--------------------------------------------------

- inverse_operation
- guess_and_check
- balance_both_sides
- undo_steps
- pattern_or_memory
- substitution_check
- equivalent_transformations
- other

Registra únicamente estrategias que el estudiante haya mostrado
realmente.

No confundas una estrategia intentada con una estrategia aplicada
correctamente.

--------------------------------------------------
7. REGLAS DE CITAS
--------------------------------------------------

Toda dimensión distinta de not_observed necesita una cita literal.

Toda etiqueta de error necesita una cita literal.

Toda intención distinta de other necesita una cita literal.

Las citas deben pertenecer exclusivamente al último mensaje
del estudiante.

Si no puedes encontrar una cita literal que respalde una
observación, descarta esa observación.

No modifiques las citas para hacerlas coincidir con tu interpretación.

--------------------------------------------------
8. REGLAS ADICIONALES
--------------------------------------------------

- "No sé" o "no entiendo" puede ser evidencia de confusión,
  pero no significa automáticamente que las tres dimensiones
  sean none.

- Una pregunta no significa automáticamente que el estudiante
  necesite una explicación.

- Una respuesta correcta no demuestra por sí sola que el
  procedimiento sea correcto.

- Una respuesta incorrecta no demuestra por sí sola qué error
  conceptual cometió el estudiante.

- Si el estudiante corrige su propio error, evalúa la corrección
  que muestra.

- Si el estudiante analiza el razonamiento de otra persona,
  evalúa su capacidad de análisis sin atribuirle los errores
  de esa persona.

- Si el mensaje es un saludo, una queja o no contiene evidencia
  matemática, utiliza intent other y todas las dimensiones
  not_observed.

- No otorgues strong por el simple hecho de que el estudiante
  utilice términos matemáticos.

- No confundas seguridad al responder con comprensión.

- No infieras conocimientos que no aparecen en el mensaje.

--------------------------------------------------
9. EJEMPLOS
--------------------------------------------------

EJEMPLO A: PROCEDIMIENTO CORRECTO

Ejercicio:
2x + 4 = 10

Mensaje:
"Primero resto 4 en ambos lados para mantener la igualdad.
Después divido entre 2 y obtengo x = 3."

Resultado esperado:
- student_intent: showing_procedure
- procedural: strong
- conceptual: partial
- relational: not_observed
- errors: []
- final_answer: 3

EJEMPLO B: PROCEDIMIENTO INCORRECTO

Ejercicio:
2x + 4 = 10

Mensaje:
"Primero dividiría ambos lados entre 3 para dejar sola la x.
Entonces x = 5. Sé que está bien porque si sustituyo el resultado
en la ecuación original, 3 por 5 es igual a 15."

Validación determinista:
{
    "status": "incorrect",
    "student_value": 5,
    "expected_value": 3
}

Resultado esperado:
- student_intent: showing_procedure
- procedural: weak
- conceptual: weak
- relational: weak
- errors: wrong_inverse_operation
- final_answer: 5

Justificación de la evaluación:
El estudiante propone una operación que no permite despejar
correctamente la variable.

La comprobación que presenta utiliza una multiplicación correcta,
pero no sustituye el valor en la ecuación original.

No debe clasificarse como strong en ninguna dimensión por
el simple hecho de explicar varios pasos.

EJEMPLO C: RESULTADO CORRECTO SIN EXPLICACIÓN

Ejercicio:
2x + 4 = 10

Mensaje:
"x = 3"

Resultado esperado:
- student_intent: giving_answer
- procedural: not_observed
- conceptual: not_observed
- relational: not_observed
- errors: []
- final_answer: 3

EJEMPLO D: RESULTADO CORRECTO CON REGLA MEMORIZADA

Ejercicio:
2x + 4 = 10

Mensaje:
"Paso el 4 restando y después divido entre 2. x = 3."

Resultado esperado:
- student_intent: showing_procedure
- procedural: strong
- conceptual: weak o partial
- relational: not_observed
- errors: rule_without_reason, únicamente si la ausencia
  de justificación es relevante para la pregunta actual.
- final_answer: 3

EJEMPLO E: ERROR ARITMÉTICO

Ejercicio:
2x = 6

Mensaje:
"Divido entre 2 y obtengo x = 4."

Validación determinista:
{
    "status": "incorrect",
    "student_value": 4,
    "expected_value": 3
}

Resultado esperado:
- procedural: partial o weak, según la evidencia.
- conceptual: partial si comprende correctamente que debe dividir.
- relational: not_observed, si no hay evidencia.
- No inventes un error conceptual.
- final_answer: 4

EJEMPLO F: ANÁLISIS DEL RAZONAMIENTO DE OTRA PERSONA

Mensaje:
"Mi compañero dice que x = 45, pero está mal porque debería
dividir 15 entre 3."

Resultado esperado:
- student_intent: evaluating_reasoning
- relational: partial o strong, según el contexto.
- errors: []
- final_answer: null

EJEMPLO G: SOLICITUD DE EXPLICACIÓN

Mensaje:
"¿Por qué tenemos que dividir entre 3?"

Resultado esperado:
- asking_question o requesting_explanation, según el contexto.
- No registres automáticamente un error.
- No marques las dimensiones como none solo por preguntar.

EJEMPLO H: CONFUSIÓN EXPLÍCITA

Mensaje:
"No entiendo cómo empezar."

Resultado esperado:
- student_intent: expressing_confusion
- procedural: none, si el ejercicio actual exige iniciar
  un procedimiento y la frase demuestra que no sabe hacerlo.
- conceptual: not_observed
- relational: not_observed

--------------------------------------------------
10. INSTRUCCIÓN FINAL
--------------------------------------------------

Analiza exclusivamente el último mensaje del estudiante.

Utiliza el ejercicio actual para determinar si sus operaciones
son pertinentes.

Utiliza la validación determinista para interpretar el resultado.

Evalúa cada dimensión de forma independiente.

Devuelve únicamente JSON válido.
No agregues texto fuera del JSON.
"""



# ---------------------------------------------------------------------------
# Utilidades de mensajes y respuestas
# ---------------------------------------------------------------------------

def _message_text(message: dict[str, Any]) -> str:
    return "".join(
        block.get("text", "")
        for block in message.get("content", [])
        if isinstance(block, dict)
        and isinstance(block.get("text"), str)
    )


def _response_text(response: dict[str, Any]) -> str:
    return "".join(
        block["text"]
        for block in response.get("output", {})
        .get("message", {})
        .get("content", [])
        if isinstance(block, dict)
        and isinstance(block.get("text"), str)
    ).strip()


def _render_user_message(
    conversation: list[dict[str, Any]],
    student_message: str,
    limit: int = 6,
) -> str:
    """Construye el contexto sin convertir el historial en evidencia nueva."""
    lines = []

    for message in conversation[:-1][-limit:]:
        role = message.get("role")
        who = "Estudiante" if role == "user" else "Tutor"
        lines.append(f"{who}: {_message_text(message)}")

    history = "\n".join(lines) or "(sin historial)"

    return (
        f"HISTORIAL RECIENTE (solo contexto):\n{history}\n\n"
        "ÚLTIMO MENSAJE DEL ESTUDIANTE (evalúa exclusivamente este):\n"
        f"<<<\n{student_message}\n>>>\n\n"
        "Devuelve únicamente el JSON solicitado."
    )


# ---------------------------------------------------------------------------
# Parseo y normalización
# ---------------------------------------------------------------------------

def _parse_json(response_text: str) -> dict[str, Any]:
    normalized = response_text.strip()

    if normalized.startswith("```"):
        lines = normalized.splitlines()
        normalized = "\n".join(lines[1:-1]).strip()

    if not normalized:
        raise ValueError("La respuesta del evaluador está vacía.")

    start = normalized.find("{")
    end = normalized.rfind("}")

    if start == -1 or end <= start:
        raise ValueError("La respuesta no contiene un objeto JSON.")

    data = json.loads(normalized[start:end + 1])

    if not isinstance(data, dict):
        raise ValueError("El JSON del evaluador no es un objeto.")

    return data


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def _quote_is_real(quote: str, message: str) -> bool:
    if not isinstance(quote, str):
        return False

    cleaned = _normalize_text(quote)
    cleaned = cleaned.replace("...", "").replace("…", "")
    cleaned = cleaned.strip(" .\"'")

    return len(cleaned) >= 2 and cleaned in _normalize_text(message)


def _normalize_evaluation(raw: dict[str, Any]) -> dict[str, Any]:
    intent = raw.get("student_intent")

    if intent not in VALID_INTENTS:
        intent = "other"

    intent_quote = raw.get("intent_quote")
    if not isinstance(intent_quote, str):
        intent_quote = ""

    # Dimensiones
    raw_dimensions = raw.get("dimensions")
    if not isinstance(raw_dimensions, dict):
        raw_dimensions = {}

    dimensions: dict[str, dict[str, str]] = {}

    for name in DIMENSIONS:
        item = raw_dimensions.get(name)

        if not isinstance(item, dict):
            item = {}

        level = item.get("level")
        quote = item.get("quote")

        dimensions[name] = {
            "level": level if level in VALID_LEVELS else "not_observed",
            "quote": quote if isinstance(quote, str) else "",
        }

    # Errores
    errors = []
    raw_errors = raw.get("errors")

    if isinstance(raw_errors, list):
        for item in raw_errors:
            if not isinstance(item, dict):
                continue

            label = item.get("label")
            quote = item.get("quote")

            if not isinstance(label, str):
                continue

            errors.append({
                "label": label,
                "quote": quote if isinstance(quote, str) else "",
            })

    # Estrategias
    raw_strategies = raw.get("strategies_used")
    strategies = []

    if isinstance(raw_strategies, list):
        strategies = list(dict.fromkeys(
            strategy
            for strategy in raw_strategies
            if isinstance(strategy, str)
            and strategy in STRATEGY_LABELS
        ))

    # Respuesta final
    final = raw.get("final_answer")

    if not isinstance(final, dict):
        final = {}

    value = final.get("value")
    quote = final.get("quote")

    return {
        "student_intent": intent,
        "intent_quote": intent_quote,
        "dimensions": dimensions,
        "errors": errors,
        "strategies_used": strategies,
        "final_answer": {
            "value": (
                str(value)
                if value not in (None, "", "null")
                else ""
            ),
            "quote": quote if isinstance(quote, str) else "",
        },
        "evaluator_failed": False,
    }


# ---------------------------------------------------------------------------
# Validación de evidencia
# ---------------------------------------------------------------------------

def _sanitize(
    evaluation: dict[str, Any],
    student_message: str,
) -> dict[str, Any]:
    """
    Elimina observaciones sin respaldo literal.

    También incorpora errores aritméticos detectados por código,
    nunca por inferencia del modelo de lenguaje.
    """
    discarded: list[str] = []

    # La intención también necesita evidencia.
    if (
        evaluation["student_intent"] != "other"
        and not _quote_is_real(
            evaluation["intent_quote"],
            student_message,
        )
    ):
        discarded.append(
            f"intent:{evaluation['student_intent']}"
        )
        evaluation["student_intent"] = "other"
        evaluation["intent_quote"] = ""

    # Dimensiones
    for name, dimension in evaluation["dimensions"].items():
        if dimension["level"] == "not_observed":
            dimension["quote"] = ""
            continue

        if not _quote_is_real(
            dimension["quote"],
            student_message,
        ):
            discarded.append(
                f"{name}:{dimension['level']}"
            )
            dimension["level"] = "not_observed"
            dimension["quote"] = ""

    # Errores
    valid_errors = []
    seen_errors = set()

    for error in evaluation["errors"]:
        label = error["label"]
        quote = error["quote"]

        if (
            label in ERROR_LABELS
            and _quote_is_real(quote, student_message)
        ):
            key = (label, _normalize_text(quote))

            if key not in seen_errors:
                valid_errors.append(error)
                seen_errors.add(key)
        else:
            discarded.append(f"error:{label}")

    # La aritmética se comprueba con código.
    for slip in find_arithmetic_slips(student_message):
        key = ("arithmetic_slip", _normalize_text(slip))

        if key not in seen_errors:
            valid_errors.append({
                "label": "arithmetic_slip",
                "quote": slip,
            })
            seen_errors.add(key)

    evaluation["errors"] = valid_errors

    # Respuesta final
    final = evaluation.get("final_answer") or {}

    token = (
        final.get("value", "")
        if isinstance(final, dict)
        else ""
    )
    quote = (
        final.get("quote", "")
        if isinstance(final, dict)
        else ""
    )

    value = parse_number(token) if token else None

    if value is not None:
        quote_is_valid = _quote_is_real(
            quote,
            student_message,
        )
        value_is_in_quote = (
            _normalize_text(str(token))
            in _normalize_text(quote)
        )

        if not quote_is_valid or not value_is_in_quote:
            discarded.append("final_answer")
            value = None

    evaluation["final_answer"] = value
    evaluation["discarded"] = discarded

    return evaluation


# ---------------------------------------------------------------------------
# Respuesta de respaldo
# ---------------------------------------------------------------------------

def _fallback_evaluation() -> dict[str, Any]:
    """
    Se utiliza cuando el modelo no devuelve JSON válido después
    de los intentos disponibles.

    No genera evidencia ficticia.
    """
    return {
        "student_intent": "other",
        "intent_quote": "",
        "dimensions": {
            name: {
                "level": "not_observed",
                "quote": "",
            }
            for name in DIMENSIONS
        },
        "errors": [],
        "strategies_used": [],
        "final_answer": None,
        "discarded": [],
        "evaluator_failed": True,
    }


# ---------------------------------------------------------------------------
# Comunicación con Bedrock
# ---------------------------------------------------------------------------

def _request_evaluation(
    client: Any,
    model_id: str,
    system_prompt: str,
    user_text: str,
) -> str:
    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_text}],
                }
            ],
            inferenceConfig={
                "temperature": 0.0,
                "maxTokens": 900,
                "topP": 0.9,
            },
        )

    except ClientError as exc:
        error_msg = (
            exc.response.get("Error", {}).get("Message", str(exc))
        )
        raise RuntimeError(
            f"Error al evaluar el mensaje en Bedrock: {error_msg}"
        ) from exc

    return _response_text(response)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def evaluate_student(
    client: Any,
    model_id: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
    student_message: str,
    current_question: str,
    answer_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Evalúa el último mensaje del estudiante.

    La validación matemática determinista se utiliza como
    referencia para evaluar el resultado final.

    El modelo de lenguaje analiza el razonamiento y las
    dimensiones pedagógicas.
    """

    # -----------------------------------------------------
    # 1. Validación matemática determinista
    # -----------------------------------------------------

    if answer_validation is None:
        validation = validate_linear_answer(
            student_message,
            state.expected_value,
        )

        answer_validation = asdict(validation)

    # -----------------------------------------------------
    # 2. Construcción del contexto del evaluador
    # -----------------------------------------------------

    system_prompt = (
        f"{EVALUATOR_PROMPT}\n\n"

        "PREGUNTA O EJERCICIO ACTUAL:\n"
        f"{current_question}\n\n"

        "ESTADO PEDAGÓGICO (solo contexto):\n"
        f"{json.dumps(state.as_prompt_context(), ensure_ascii=False)}\n\n"

        "VALIDACIÓN MATEMÁTICA DETERMINISTA:\n"
        f"{json.dumps(answer_validation, ensure_ascii=False)}\n\n"

        "REGLA OBLIGATORIA:\n"
        "- Respeta el resultado de la validación determinista.\n"
        "- No consideres correcto un resultado cuyo status sea incorrect.\n"
        "- No confundas un resultado correcto con un procedimiento correcto.\n"
        "- Evalúa las tres dimensiones de manera independiente.\n"
        "- No inventes evidencias ni procedimientos."
    )

    # -----------------------------------------------------
    # 3. Construcción del mensaje del estudiante
    # -----------------------------------------------------

    user_text = _render_user_message(
        conversation,
        student_message,
    )

    # -----------------------------------------------------
    # 4. Solicitud al modelo
    # -----------------------------------------------------

    for attempt in range(2):

        request_text = user_text

        if attempt:
            request_text += JSON_REMINDER

        response_text = _request_evaluation(
            client,
            model_id,
            system_prompt,
            request_text,
        )

        try:
            raw = _parse_json(response_text)

        except (json.JSONDecodeError, ValueError):
            continue

        normalized = _normalize_evaluation(raw)

        evaluation = _sanitize(
            normalized,
            student_message,
        )

        # -------------------------------------------------
        # 5. Sincronizar respuesta final con el validador
        # -------------------------------------------------

        if answer_validation.get("student_value") is not None:
            evaluation["final_answer"] = (
                answer_validation["student_value"]
            )

        # Guardar la validación para el motor pedagógico.
        evaluation["validation"] = answer_validation.get(
            "status",
            "unrecognized",
        )

        return evaluation

    # -----------------------------------------------------
    # 6. Respuesta de respaldo
    # -----------------------------------------------------

    fallback = _fallback_evaluation()

    fallback["validation"] = answer_validation.get(
        "status",
        "unrecognized",
    )

    return fallback

