# Kaanbal Tech

> **IA que enseña a pensar, no solo a contestar.**

Kaanbal es un prototipo de tutor de matemáticas para estudiantes de secundaria. En lugar de entregar directamente la respuesta, intenta identificar qué entiende el estudiante, detectar señales de confusión y elegir una intervención pedagógica: una pregunta diagnóstica, una representación concreta o visual, una explicación guiada, práctica independiente o un reto conceptual.

El proyecto participa en el reto de UniconHub: **IA que enseña a pensar**.

## El problema

En México, solo el 34% de los estudiantes alcanzó el nivel mínimo de competencia matemática en PISA 2022. La disponibilidad de respuestas generadas por IA puede ocultar la brecha de aprendizaje si el estudiante obtiene el resultado sin construir el razonamiento.

Kaanbal busca que la IA funcione como andamiaje: ayuda a avanzar, pero conserva el esfuerzo cognitivo del estudiante y solicita evidencia de comprensión.

## Cómo va actualmente

El repositorio contiene un **MVP técnico de conversación en Python** conectado a Amazon Bedrock:

- Un evaluador pedagógico analiza la intención, la señal de comprensión, la evidencia y posibles misconceptions del último mensaje.
- Un motor pedagógico selecciona la siguiente estrategia con base en el desempeño observado.
- Un tutor genera la intervención sin resolver automáticamente el ejercicio.
- El estado de la sesión conserva dominio conceptual, dominio procedimental y relacional, confianza, historial de estrategias, intentos y próximos pasos.
- Un validador específico para ecuaciones lineales comprueba respuestas como `x = 5` y detecta si el estudiante incluyó una justificación.
- Un administrador selecciona ejercicios de ecuaciones lineales con dificultad progresiva.
- La transferencia se marca cuando el estudiante resuelve un ejercicio de mayor dificultad, justifica su procedimiento y necesita pocas pistas.

### Flujo actual

```text
Mensaje del estudiante
        ↓
Validación matemática + contexto de sesión
        ↓
Evaluador pedagógico (JSON estructurado)
        ↓
Motor de estrategias y actualización del estado
        ↓
Tutor adaptativo con pistas y límites de profundidad
        ↓
Siguiente intervención
```

## Estructura

```text
.
├── main.py                     # Entrada CLI y orquestación de cada turno
└── app/
    ├── ai/
    │   ├── evaluator.py         # Evaluación pedagógica con Bedrock
    │   └── tutor.py             # Generación de la intervención
    ├── core/
    │   ├── answer_validator.py  # Validación de respuestas de ecuaciones
    │   ├── exercise_manager.py  # Banco y progresión de ejercicios
    │   ├── pedagogical_engine.py# Selección de estrategia y transferencia
    │   └── state.py             # Estado pedagógico de la sesión
    └── models/
```

## Requisitos

- Python 3.10+
- Credenciales de AWS con acceso a Amazon Bedrock
- Un modelo habilitado en la región configurada, por ejemplo `us.amazon.nova-pro-v1:0`

Las dependencias actuales son `boto3`, `botocore` y `python-dotenv`. Todavía falta formalizarlas en un `requirements.txt` o `pyproject.toml`.

## Ejecución local

1. Instala las dependencias:

   ```bash
   pip install boto3 botocore python-dotenv
   ```

2. Configura tus credenciales de AWS mediante el mecanismo estándar de AWS y, opcionalmente, crea un archivo `.env`:

   ```env
   AWS_REGION=us-east-1
   BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
   ```

3. Ejecuta el tutor:

   ```bash
   python main.py
   ```

4. Escribe `salir` para terminar. El programa muestra también el estado pedagógico de depuración de la sesión.

> No subas credenciales, claves de AWS ni archivos `.env` al repositorio.

## Ejecución con Docker

Configura `backend/.env` con `SUPABASE_URL` y una clave de servidor de Supabase (`SUPABASE_SERVICE_ROLE_KEY` o `SUPABASE_SECRET_KEY`). Para usar el tutor de IA, configura también las credenciales de AWS y, opcionalmente, `AWS_REGION` y `BEDROCK_MODEL_ID` en `ia/.env`.

Desde la raíz del repositorio, construye y levanta los servicios:

```bash
docker compose up --build -d
```

La interfaz queda disponible en `http://localhost:3000` y la API en `http://localhost:3001`. El contenedor `ia` ejecuta la interfaz de consola interactiva; para interactuar con ella usa `docker compose run --rm ia`. Si la API se sirve desde otro host, define `VITE_API_URL` antes de construir el frontend.

## Qué falta

Este proyecto todavía es un prototipo y no una plataforma lista para estudiantes o docentes. Los pendientes principales son:

- **Interfaz de usuario:** reemplazar la CLI por una experiencia web o móvil accesible para estudiantes.
- **Diagnóstico inicial:** crear una evaluación breve que estime el nivel antes de comenzar y cubra más habilidades que ecuaciones lineales.
- **Contenido:** ampliar el banco de ejercicios, las representaciones y las rutas de aprendizaje para aritmética, álgebra, geometría y problemas contextualizados.
- **Evaluación del razonamiento:** mejorar la validación para entender pasos matemáticos reales, no solo patrones de texto como `x = ...`.
- **Persistencia y perfiles:** guardar sesiones, progreso y grupos para que un docente pueda atender un salón de 45 estudiantes.
- **Panel docente:** mostrar avances, errores frecuentes, confianza y recomendaciones sin exponer respuestas innecesarias.
- **Seguridad y privacidad:** definir autenticación, protección de datos de menores, límites de uso y controles de contenido.
- **Calidad técnica:** agregar `requirements.txt` o `pyproject.toml`, pruebas automatizadas, manejo de costos y observabilidad de Bedrock.
- **Validación educativa:** probar con estudiantes y docentes, medir aprendizaje transferible y ajustar las estrategias con evidencia.

## Próximo objetivo del hackatón

Convertir este núcleo en una demo de extremo a extremo con:

1. Una pantalla de conversación para el estudiante.
2. Un flujo inicial de diagnóstico de ecuaciones lineales.
3. Un ejemplo visible de cómo Kaanbal da una pista en vez de revelar la respuesta.
4. Un indicador de progreso basado en justificación y transferencia.
5. Una vista simple para que el docente observe el estado de varios estudiantes.

## Estado del proyecto

**Fase:** MVP técnico / prototipo de tutor adaptativo.

**Prioridad actual:** demostrar que la IA puede evaluar el razonamiento y adaptar sus pistas sin sustituir el proceso de resolución del estudiante.

## Equipo y contexto

Kaanbal Tech se desarrolla para el hackatón de UniconHub por [TheIgratxd](https://github.com/TheIgratxd).
