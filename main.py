import os
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Any

load_dotenv()

SYSTEM_PROMPT = """
IDENTIDAD
Eres Kaanbal, un tutor de matemáticas para estudiantes
de aproximadamente 15 años.

Tu propósito es ayudar a desarrollar comprensión matemática,
razonamiento y autonomía. No eres simplemente un solucionador
de ejercicios.

PRINCIPIOS PEDAGÓGICOS
- Prioriza la comprensión sobre memorizar procedimientos.
- Identifica posibles errores conceptuales a partir de evidencias.
- No consideres un error aislado como una dificultad permanente.
- Utiliza preguntas, pistas y contraejemplos.
- Pide al alumno que justifique sus procedimientos.
- Adapta la dificultad a las respuestas del alumno.

INTERACCIÓN
- Si el estudiante saluda, responde naturalmente.
  No introduzcas ejercicios sin contexto.
- Si pregunta por un concepto, explica con claridad y
  utiliza ejemplos cuando sean pertinentes.
- Si intenta resolver un ejercicio, analiza su procedimiento.
- Si se equivoca, evita revelar inmediatamente la solución.
  Ayúdalo a identificar dónde pudo equivocarse.
- Si no sabe cómo continuar, proporciona una pista gradual.
- Si solicita la respuesta directamente, intenta promover
  el razonamiento, pero no conviertas cada interacción
  en una interrogación interminable.
- Si una explicación directa es necesaria, puedes darla
  y después comprobar la comprensión con una pregunta.

DIAGNÓSTICO
- No etiquetes al estudiante.
- Formula hipótesis sobre sus conocimientos, no conclusiones
  definitivas.
- Toda hipótesis debe estar respaldada por evidencias.
- Cuando no exista suficiente evidencia, continúa explorando.

AUTONOMÍA
- Busca que el alumno pueda resolver problemas por sí mismo.
- Cuando el proceso de aprendizaje lo permita, presenta
  un problema nuevo que pueda resolver sin ayuda.
- No afirmes que ha aprendido algo únicamente porque
  haya leído o repetido una explicación.

ESTILO
- Habla en español claro y natural.
- Sé paciente, pero no infantilices al estudiante.
- Evita respuestas innecesariamente largas.
- No generes ejercicios de forma automática en cada mensaje.

CONTROL DE PISTAS
- Si detectas un error, no muestres de inmediato el procedimiento completo.
- Empieza con una pregunta diagnóstica o una pista breve.
- Aumenta gradualmente la precisión de las pistas en turnos posteriores.
- Solo muestra el procedimiento completo cuando el alumno lo haya intentado
  varias veces, lo solicite explícitamente después de recibir pistas, o sea
  necesario para corregir una explicación.

REGLA DE ADAPTACIÓN ANTE LA FALTA DE COMPRENSIÓN

- Si el alumno dice que no entiende una explicación, no la repitas
  con las mismas palabras ni te limites a hacerla más larga.

- Cambia de estrategia pedagógica. Puedes utilizar ejemplos
  concretos, analogías, representaciones visuales, números
  sencillos o problemas más elementales.

- Antes de enseñar un procedimiento, identifica qué prerequisito
  podría estar faltando mediante una pregunta sencilla.

- No asumas que el alumno tiene dificultades con todo el concepto.
  Aísla la dificultad mediante preguntas breves.

- Si el alumno responde "no sé", no repitas inmediatamente
  la pregunta ni reveles toda la solución. Reduce la dificultad
  de la tarea y proporciona una pista que le permita avanzar.

- Evita hacer varias preguntas simultáneamente. Presenta una
  pregunta concreta y espera la respuesta del alumno.

- Si ya explicaste un procedimiento, no lo vuelvas a ejecutar
  automáticamente en el siguiente ejercicio.

TRANSFERENCIA DE CONOCIMIENTO

- Cuando el alumno afirme haber comprendido un concepto,
  no asumas que ya lo domina.

- Presenta un ejercicio nuevo, de dificultad similar, y permite
  que el alumno lo intente sin mostrar previamente el procedimiento.

- No resuelvas el ejercicio de transferencia antes de que el
  alumno tenga la oportunidad de intentarlo.

- Evalúa la comprensión a partir de su procedimiento, respuesta
  y justificación, no únicamente de si obtuvo el resultado correcto.

- Si resuelve correctamente, solicita una justificación breve
  o una comprobación, sin convertirlo en un interrogatorio.

- Si falla, utiliza la evidencia de su intento para decidir
  cuál es la siguiente intervención pedagógica.

ESTADO PEDAGÓGICO
Al final de cada respuesta incluye exactamente un bloque oculto con este formato:
<PEDAGOGICAL_STATE>{"concept":"...", "learning_evidence":["..."],
"misconception_hypotheses":[]}</PEDAGOGICAL_STATE>
El contenido debe ser JSON válido. Conserva las respuestas anteriores del alumno,
pero registra en learning_evidence únicamente evidencias de razonamiento,
procedimientos, errores conceptuales o comprensión; no incluyas saludos o
mensajes administrativos. Actualiza el concepto trabajado y describe el siguiente
paso concreto. No incluyas niveles, estrategia ni estimaciones: Python decide
esos campos mediante el motor pedagógico.
No menciones ni expliques este bloque al alumno.
"""

TEACHING_STRATEGIES = frozenset(
    {
        "guided_discovery",
        "concrete_representation",
        "visual_representation",
        "worked_example",
        "error_analysis",
        "transfer_practice",
        "diagnostic_question",
        "independent_practice",
        "conceptual_challenge",
    }
)
MAX_PEDAGOGICAL_LEVEL = 4
CONFUSION_MARKERS = ("no entiendo", "no sé", "no se", "sigo confundido")


@dataclass(frozen=True)
class PedagogicalDecision:
  strategy: str
  hint_level: int
  scaffolding_level: int
  required_evidence: str
  transfer_ready: bool


def select_strategy(state: "PedagogicalState") -> PedagogicalDecision:
  if state.confidence < 0.3:
    strategy = "diagnostic_question"
  elif state.mastery_estimate < 0.3:
    strategy = "concrete_representation"
  elif state.mastery_estimate < 0.6:
    strategy = "visual_representation"
  elif not state.transfer_verified:
    strategy = "independent_practice"
  else:
    strategy = "conceptual_challenge"

  latest_evidence = " ".join(state.learning_evidence[-2:]).lower()
  if (
      state.strategy_history
      and state.strategy_history[-1] == strategy
      and any(marker in latest_evidence for marker in CONFUSION_MARKERS)
  ):
    strategy = {
        "diagnostic_question": "concrete_representation",
        "concrete_representation": "visual_representation",
        "visual_representation": "worked_example",
        "independent_practice": "diagnostic_question",
    }.get(strategy, "guided_discovery")

  support_by_strategy = {
      "diagnostic_question": (0, 4, "Una respuesta que revele el prerequisito."),
      "concrete_representation": (1, 3, "Una relación con un ejemplo concreto."),
      "visual_representation": (2, 2, "Una representación o comparación visual."),
      "worked_example": (2, 2, "La justificación de un paso del ejemplo."),
      "independent_practice": (1, 1, "Un intento independiente y su justificación."),
      "conceptual_challenge": (0, 0, "Una explicación o conexión conceptual."),
      "guided_discovery": (1, 2, "Una respuesta razonada a una pregunta guía."),
  }
  hint_level, scaffolding_level, required_evidence = support_by_strategy[strategy]
  return PedagogicalDecision(
      strategy=strategy,
      hint_level=hint_level,
      scaffolding_level=scaffolding_level,
      required_evidence=required_evidence,
      transfer_ready=(
          state.mastery_estimate >= 0.6
          and state.confidence >= 0.5
          and not state.transfer_verified
      ),
  )


@dataclass
class PedagogicalState:
  concept: str = ""
  mastery_estimate: float = 0.0
  confidence: float = 0.0
  autonomy_estimate: float = 0.0
  hint_level: int = 0
  scaffolding_level: int = 0
  teaching_strategy: str = "guided_discovery"
  learning_evidence: list[str] = field(default_factory=list)
  misconception_hypotheses: list[str] = field(default_factory=list)
  attempt_count: int = 0
  transfer_verified: bool = False
  next_step: str = ""
  strategy_history: list[str] = field(default_factory=list)

  def as_prompt_context(self) -> str:
    return json.dumps(
        {
            "concept": self.concept,
            "mastery_estimate": self.mastery_estimate,
            "confidence": self.confidence,
            "autonomy_estimate": self.autonomy_estimate,
            "hint_level": self.hint_level,
            "scaffolding_level": self.scaffolding_level,
            "teaching_strategy": self.teaching_strategy,
            "learning_evidence": self.learning_evidence,
            "misconception_hypotheses": self.misconception_hypotheses,
            "attempt_count": self.attempt_count,
            "transfer_verified": self.transfer_verified,
            "next_step": self.next_step,
            "strategy_history": self.strategy_history,
        },
        ensure_ascii=False,
    )

  def update(self, values: dict[str, Any]) -> None:
    """Apply only model proposals that Python can validate safely."""
    concept = values.get("concept")
    next_step = values.get("next_step")
    evidence = values.get("learning_evidence")
    hypotheses = values.get("misconception_hypotheses")

    if isinstance(concept, str):
      self.concept = concept
    if isinstance(next_step, str):
      self.next_step = next_step
    if isinstance(evidence, list) and all(
        isinstance(item, str) for item in evidence
    ):
      self.learning_evidence = evidence
    if isinstance(hypotheses, list) and all(
        isinstance(item, str) for item in hypotheses
    ):
      self.misconception_hypotheses = hypotheses

  def register_attempt(self) -> None:
    self.attempt_count += 1

  def apply_decision(self, decision: PedagogicalDecision) -> None:
    self.teaching_strategy = decision.strategy
    self.hint_level = decision.hint_level
    self.scaffolding_level = decision.scaffolding_level
    self.strategy_history.append(decision.strategy)
    self.strategy_history = self.strategy_history[-5:]

  def apply_assessment(
      self,
      *,
      mastery_estimate: float,
      confidence: float,
      autonomy_estimate: float,
  ) -> None:
    """Update estimates produced by a trusted Python evaluator."""
    estimates = (mastery_estimate, confidence, autonomy_estimate)
    if not all(0.0 <= estimate <= 1.0 for estimate in estimates):
      raise ValueError("Las estimaciones pedagógicas deben estar entre 0 y 1.")
    self.mastery_estimate = mastery_estimate
    self.confidence = confidence
    self.autonomy_estimate = autonomy_estimate

  def mark_transfer_verified(self) -> None:
    self.transfer_verified = True


STATE_START = "<PEDAGOGICAL_STATE>"
STATE_END = "</PEDAGOGICAL_STATE>"


def extract_reply_and_state(
    response_text: str, state: PedagogicalState
) -> str:
  block_start = response_text.find(STATE_START)
  if block_start == -1:
    return response_text.strip()

  payload_start = block_start + len(STATE_START)
  payload = response_text[payload_start:].lstrip()
  decoder = json.JSONDecoder()
  try:
    state_data, payload_end = decoder.raw_decode(payload)
  except json.JSONDecodeError:
    return response_text[:block_start].strip()

  closing_marker = payload[payload_end:].lstrip()
  if not closing_marker.startswith(STATE_END):
    return response_text[:block_start].strip()

  if isinstance(state_data, dict):
    state.update(state_data)
  closing_start = (
      payload_start
      + len(payload)
      - len(closing_marker)
  )
  closing_end = closing_start + len(STATE_END)
  return (
      response_text[:block_start] + response_text[closing_end:]
  ).strip()


def run_converse(
    prompt: str,
    model_id: str,
    region: str,
    conversation: list[dict[str, Any]] | None = None,
    pedagogical_state: PedagogicalState | None = None,
) -> str:
  client = boto3.client("bedrock-runtime", region_name=region)
  conversation = conversation if conversation is not None else []
  pedagogical_state = (
      pedagogical_state
      if pedagogical_state is not None
      else PedagogicalState()
  )
  pedagogical_state.register_attempt()
  decision = select_strategy(pedagogical_state)
  pedagogical_state.apply_decision(decision)
  system_prompts = [
    {
        "text": (
            f"{SYSTEM_PROMPT}\n\n"
            "ESTADO ACTUAL DE LA SESIÓN:\n"
            f"{pedagogical_state.as_prompt_context()}\n\n"
            "DECISIÓN DEL MOTOR PEDAGÓGICO DE PYTHON:\n"
            f"{json.dumps(decision.__dict__, ensure_ascii=False)}\n"
            "Sigue esta estrategia y busca la evidencia indicada. "
            "No la sustituyas por otra."
        )
    }
  ]

  conversation.append({"role": "user", "content": [{"text": prompt}]})

  inference_config = {
      "temperature": 0.3,
      "maxTokens": 1024,
      "topP": 0.9,
  }

  try:
    response = client.converse(
        modelId=model_id,
        system=system_prompts,
        messages=conversation,
        inferenceConfig=inference_config,
    )

    content_blocks = response["output"]["message"]["content"]
    reply_text = "".join(
        block["text"] for block in content_blocks if "text" in block
    )

    usage = response.get("usage", {})
    print(
        f"\n[Tokens -> entrada: {usage.get('inputTokens', 0)}, "
        f"salida: {usage.get('outputTokens', 0)}, "
        f"total: {usage.get('totalTokens', 0)}]"
    )
    visible_reply = extract_reply_and_state(reply_text, pedagogical_state)
    conversation.append(
        {"role": "assistant", "content": [{"text": visible_reply}]}
    )
    return visible_reply

  except ClientError as exc:
    error_msg = exc.response.get("Error", {}).get("Message", str(exc))
    raise RuntimeError(f"Error al invocar Bedrock Converse: {error_msg}") from exc


if __name__ == "__main__":
  region_name = os.getenv("AWS_REGION", "us-east-1")
  # Cambia el model_id por el ID o inference profile del modelo que uses en Bedrock
  default_model = os.getenv(
      "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
  )

  conversation: list[dict[str, Any]] = []
  pedagogical_state = PedagogicalState()

  print("Kaanbal está listo. Escribe 'salir' para terminar.")
  while True:
    prompt = input("\nTú: ").strip()
    if prompt.lower() in {"salir", "exit", "quit"}:
      break
    if not prompt:
      continue

    answer = run_converse(
        prompt=prompt,
        model_id=default_model,
        region=region_name,
        conversation=conversation,
        pedagogical_state=pedagogical_state,
    )
    print(f"\nKaanbal: {answer}")

    print("\n[DEBUG - ESTADO PEDAGÓGICO]")
    print(pedagogical_state.as_prompt_context())