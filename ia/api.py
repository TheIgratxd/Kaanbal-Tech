import os
from dataclasses import asdict, fields
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ia.main import process_student_message
from ia.app.core.diagnostic import (
    DIAGNOSTIC_ITEMS,
    intro_message,
    set_diagnostic_item,
)
from ia.app.core.state import Estimate, Hypothesis, PedagogicalState


app = FastAPI(
    title="Kaanbal AI Service",
    description="Servicio de inteligencia artificial de Kaanbal",
    version="1.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    conversation: list[dict[str, Any]] = Field(default_factory=list)
    pedagogical_state: dict[str, Any]



def restore_pedagogical_state(data: dict[str, Any]) -> PedagogicalState:
    """
    Reconstruye el estado pedagógico recibido como JSON
    y convierte los diccionarios anidados en dataclasses.
    """

    valid_fields = {
        field.name
        for field in fields(PedagogicalState)
    }

    state_data = {
        key: value
        for key, value in data.items()
        if key in valid_fields
    }

    # Reconstruir estimaciones
    for dimension in ("procedural", "conceptual", "relational"):
        estimate_data = state_data.get(dimension, {})

        if isinstance(estimate_data, Estimate):
            continue

        if not isinstance(estimate_data, dict):
            estimate_data = {}

        state_data[dimension] = Estimate(
            **estimate_data
        )

    # Reconstruir hipótesis.
    raw_hypotheses = state_data.get("hypotheses", [])

    # Compatibilidad con el formato anterior de diccionario.
    if isinstance(raw_hypotheses, dict):
        raw_hypotheses = [
            {
                "label": key,
                **value,
            }
            for key, value in raw_hypotheses.items()
            if isinstance(value, dict)
        ]

    if not isinstance(raw_hypotheses, list):
        raw_hypotheses = []

    restored_hypotheses = []

    for item in raw_hypotheses:
        if isinstance(item, Hypothesis):
            restored_hypotheses.append(item)

        elif isinstance(item, dict):
            restored_hypotheses.append(
                Hypothesis(
                    label=item.get("label", "unknown"),
                    kind=item.get("kind", "unknown"),
                    confidence=float(
                        item.get("confidence", 0.25)
                    ),
                    evidence=item.get("evidence", []),
                    status=item.get("status", "active"),
                )
            )

    state_data["hypotheses"] = restored_hypotheses

    return PedagogicalState(**state_data)



@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "kaanbal-ai",
        "message": "Kaanbal IA está funcionando correctamente",
    }


@app.post("/sessions/start")
async def start_session():
    """
    Inicializa una sesión de aprendizaje con el diagnóstico.
    """

    state = PedagogicalState()

    set_diagnostic_item(state, state.diagnostic_index)

    return {
        "message": (
            f"{intro_message()}\n\n"
            f"{DIAGNOSTIC_ITEMS[state.diagnostic_index].statement}"
        ),
        "conversation": [],
        "pedagogical_state": asdict(state),
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Procesa un mensaje del alumno y devuelve la respuesta
    junto con el historial y el estado pedagógico actualizado.
    """

    prompt = request.prompt.strip()

    if not prompt:
        raise HTTPException(
            status_code=400,
            detail="El mensaje no puede estar vacío.",
        )

    try:
        state = restore_pedagogical_state(
            request.pedagogical_state
        )

        conversation = request.conversation.copy()

        model_id = os.getenv(
            "BEDROCK_MODEL_ID",
            "us.amazon.nova-pro-v1:0",
        )

        region = os.getenv(
            "AWS_REGION",
            "us-east-2",
        )

        reply = process_student_message(
            prompt=prompt,
            model_id=model_id,
            region=region,
            conversation=conversation,
            pedagogical_state=state,
        )

        return {
            "reply": reply,
            "conversation": conversation,
            "pedagogical_state": asdict(state),
        }

    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error al procesar el mensaje: {str(exc)}",
        ) from exc
