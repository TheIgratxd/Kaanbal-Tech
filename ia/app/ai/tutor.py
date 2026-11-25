
from __future__ import annotations

from typing import Any

from ia.app.core.state import PedagogicalState


HINT_LADDER = {
    0: "No des pistas adicionales si el estudiante puede continuar solo.",
    1: "Ofrece una pista breve que oriente el siguiente paso.",
    2: "Divide el problema en una pregunta pequeña.",
    3: "Muestra una parte del procedimiento y pide que continúe.",
    4: "Ofrece una explicación guiada y concreta, sin resolver todo automáticamente.",
}


TUTOR_PROMPT = """
Eres Kaanbal, un tutor de matemáticas que acompaña a estudiantes de
aproximadamente 15 años.

Tu objetivo no es entregar respuestas automáticamente, sino ayudar al
estudiante a construir su propio razonamiento.

REGLAS GENERALES

1. Responde en español claro y natural.
2. Usa un tono respetuoso, cercano y paciente.
3. No infantilices al estudiante.
4. No afirmes que comprendió algo si no hay evidencia.
5. No repitas preguntas del diagnóstico.
6. Evita explicaciones excesivamente largas.
7. Utiliza notación matemática sencilla.
8. Formula como máximo una pregunta por respuesta.
9. Procura no superar las 120 palabras.
10. No reveles directamente la solución completa cuando el estudiante
    todavía puede construirla por sí mismo.

ESTRATEGIAS

guided_explanation:
Acompaña al estudiante paso a paso. Explica una idea y permite que
continúe con el siguiente paso.

concrete_representation:
Utiliza cantidades, objetos o situaciones sencillas para explicar
el significado de las operaciones.

visual_representation:
Utiliza esquemas textuales, relaciones y representaciones sencillas.

conceptual_challenge:
Propón una pregunta que permita comprobar si comprende por qué funciona
un procedimiento. No repitas el diagnóstico.

independent_practice:
Presenta el nuevo ejercicio activo y permite que lo resuelva sin pistas
innecesarias.

diagnostic_question:
Solo se utiliza durante la fase de diagnóstico. No reinicies el diagnóstico
durante la práctica.

USO DE PISTAS

Respeta el nivel de ayuda indicado por el estado pedagógico.
No entregues una solución completa cuando el nivel de ayuda sea bajo.

EVIDENCIA

El perfil es una estimación provisional, no una etiqueta permanente.
No afirmes que el estudiante domina una dimensión únicamente por una
respuesta correcta.
No confundas pedir ayuda con no saber matemáticas.

EJERCICIOS

Si existe un ejercicio activo, trabaja sobre él.
Si el motor pedagógico activó un ejercicio nuevo, preséntalo de manera
natural.
No inventes un resultado esperado ni reveles la respuesta almacenada
internamente.

CONTEXTO

El estado pedagógico y el historial son información para adaptar tu
enseñanza. No los muestres al estudiante.
"""


def _profile_summary(state: PedagogicalState) -> str:
    profile = state.profile or {}
    baseline = state.diagnostic_profile or {}

    return (
        "PERFIL ACTUAL:\n"
        f"{profile}\n\n"
        "PERFIL INICIAL DEL DIAGNÓSTICO:\n"
        f"{baseline}"
    )


def _hint_instruction(state: PedagogicalState) -> str:
    level = max(0, min(4, int(state.hint_level)))
    return HINT_LADDER[level]


def _state_context(state: PedagogicalState) -> str:
    context = state.as_prompt_context()

    # El tutor no necesita conocer las respuestas esperadas.
    active_exercise = context.get("active_exercise", {})
    if isinstance(active_exercise, dict):
        active_exercise.pop("expected_value", None)

    # Tampoco necesita recibir las respuestas internas de ejercicios
    # ya completados.
    completed = context.get("completed_exercises", [])
    if isinstance(completed, list):
        context["completed_exercises"] = [
            {
                key: value
                for key, value in exercise.items()
                if key != "expected_value"
            }
            for exercise in completed
            if isinstance(exercise, dict)
        ]

    return str(context)


def _response_text(response: dict[str, Any]) -> str:
    return "".join(
        block.get("text", "")
        for block in response.get("output", {})
        .get("message", {})
        .get("content", [])
        if isinstance(block, dict)
        and isinstance(block.get("text"), str)
    ).strip()


def generate_tutor_response(
    client: Any,
    model_id: str,
    prompt: str,
    conversation: list[dict[str, Any]],
    state: PedagogicalState,
) -> str:
    system_prompt = (
        f"{TUTOR_PROMPT}\n\n"
        f"FASE ACTUAL: {state.phase}\n"
        f"ESTRATEGIA SELECCIONADA: {state.teaching_strategy}\n"
        f"NIVEL DE ANDAMIAJE: {state.scaffolding_level}\n"
        f"NIVEL DE PISTA: {state.hint_level}\n"
        f"INSTRUCCIÓN DE PISTA: {_hint_instruction(state)}\n\n"
        f"{_profile_summary(state)}\n\n"
        "ESTADO PEDAGÓGICO:\n"
        f"{_state_context(state)}"
    )

    messages = []

    for message in conversation:
        role = message.get("role")

        if role not in {"user", "assistant"}:
            continue

        content = message.get("content", [])

        if not isinstance(content, list):
            continue

        valid_content = [
            item
            for item in content
            if isinstance(item, dict)
            and isinstance(item.get("text"), str)
        ]

        if valid_content:
            messages.append({
                "role": role,
                "content": valid_content,
            })

    # Bedrock necesita al menos un mensaje del usuario.
    if not messages or messages[-1]["role"] != "user":
        messages.append({
            "role": "user",
            "content": [{"text": prompt}],
        })

    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={
                "temperature": 0.3,
                "maxTokens": 600,
                "topP": 0.9,
            },
        )

    except Exception as exc:
        raise RuntimeError(
            f"Error al generar la respuesta del tutor: {exc}"
        ) from exc

    text = _response_text(response)

    if not text:
        raise RuntimeError(
            "El tutor devolvió una respuesta vacía."
        )

    return text
