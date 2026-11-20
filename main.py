import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

prompt = input("Escribe tu pregunta: ")


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
"""


def run_converse(prompt: str, model_id: str, region: str) -> str:
  client = boto3.client("bedrock-runtime", region_name=region)

  system_prompts = [
    {"text": SYSTEM_PROMPT}
  ]

  messages = [{"role": "user", "content": [{"text": prompt}]}]

  inference_config = {
      "temperature": 0.3,
      "maxTokens": 1024,
      "topP": 0.9,
  }

  try:
    response = client.converse(
        modelId=model_id,
        system=system_prompts,
        messages=messages,
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
    return reply_text

  except ClientError as exc:
    error_msg = exc.response.get("Error", {}).get("Message", str(exc))
    raise RuntimeError(f"Error al invocar Bedrock Converse: {error_msg}") from exc


if __name__ == "__main__":
  region_name = os.getenv("AWS_REGION", "us-east-1")
  # Cambia el model_id por el ID o inference profile del modelo que uses en Bedrock
  default_model = os.getenv(
      "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
  )

  answer = run_converse(
      prompt=prompt,
      model_id=default_model,
      region=region_name,
  )
  print(answer)