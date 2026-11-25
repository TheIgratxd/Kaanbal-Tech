# Kaanbal Tech

> **IA que enseña a pensar, no solo a contestar.**

Kaanbal es un prototipo de tutor de matemáticas para estudiantes de secundaria ($1.^{\circ}$, $2.^{\circ}$ y $3.^{\circ}$ grado, alineado con los planes de estudio de la SEP). En lugar de entregar directamente la respuesta, intenta identificar qué entiende el estudiante, detectar señales de confusión y elegir una intervención pedagógica: una pregunta diagnóstica, una representación concreta o visual, una explicación guiada, práctica independiente o un reto conceptual.

El proyecto participa en el reto de UniconHub: **IA que enseña a pensar**.

## El problema

En México, solo el $34\%$ de los estudiantes alcanzó el nivel mínimo de competencia matemática en PISA 2022. La disponibilidad de respuestas generadas por IA puede ocultar la brecha de aprendizaje si el estudiante obtiene el resultado sin construir el razonamiento.

Kaanbal busca que la IA funcione como andamiaje: ayuda a avanzar, pero conserva el esfuerzo cognitivo del estudiante y solicita evidencia de comprensión.

## Cómo va actualmente

El repositorio contiene una aplicación web conectada con una API de usuarios y diagnóstico en Supabase, y un **tutor adaptativo en Python** conectado a Amazon Bedrock:

- **Evaluación y andamiaje pedagógico:** un evaluador analiza la intención, la señal de comprensión, la evidencia y posibles *misconceptions* del último mensaje; un motor pedagógico selecciona la siguiente estrategia y el tutor genera la intervención sin resolver automáticamente el ejercicio.
- **Estado de la sesión:** conserva dominio conceptual, dominio procedimental y relacional, confianza, historial de estrategias, intentos, transferencia y próximos pasos.
- **Validación y progresión:** incluye validación determinista para respuestas (como ecuaciones lineales) apoyada en el evaluador, selección progresiva de ejercicios y detección de transferencia cuando el estudiante resuelve ejercicios de mayor dificultad con justificación y pocas pistas.
- **Examen diagnóstico y base de preguntas:** cuenta con flujo de selección de nivel/grado, persistencia en Supabase (`students`, `academic_info`, `student_answers`, `student_skill`) y cargas estructuradas mediante CSV (`questions.csv` y `options.csv`) para `questions` y `options` cubriendo $1.^{\circ}$, $2.^{\circ}$ y $3.^{\circ}$ de secundaria (con notación matemática segura como `*`, `/`, `^`, `sqrt()` y `pi` y tipos compatibles con `questions_question_type_check`: `multiple_choice`, `true_false`, `open` y `problem`).
- **Autenticación y perfil:** `GET /users/me` resuelve el usuario autenticado directamente desde `req.user` (`SupabaseAuthGuard`) sin depender de una tabla pública `users`.

### Flujo del tutor IA

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

## Estructura del repositorio

```text
.
├── frontend/                    # React/Vite: autenticación, panel, diagnóstico y tutor
├── backend/                     # NestJS: autenticación, perfil, panel y diagnóstico (Supabase)
├── ia/                          # FastAPI (api.py), motor pedagógico (main.py), pruebas y requirements.txt
├── docker-compose.yml           # Orquestación de los tres servicios
└── README.md
```

## Requisitos

- Node.js y npm (para `frontend/` y `backend/`)
- Python 3.10+ (para `ia/`)
- Proyecto y credenciales de Supabase (`SUPABASE_URL`, clave de servidor `SUPABASE_SERVICE_ROLE_KEY` o `SUPABASE_SECRET_KEY`, y variables `VITE_*` en el frontend)
- Credenciales de AWS con acceso a Amazon Bedrock y un modelo habilitado en la región configurada (por ejemplo `us.amazon.nova-pro-v1:0`)

Las dependencias de Python están formalizadas en `ia/requirements.txt` (`boto3==1.42.17`, `python-dotenv==1.2.1`, `fastapi`, `uvicorn[standard]`).

## Ejecución local

### 1. Servicio de IA (`ia/`)

1. Crea y activa un entorno virtual e instala dependencias desde `ia/requirements.txt`:

   ```bash
   python -m venv ia/.venv
   # Windows (PowerShell):
   ia\.venv\Scripts\activate
   # Linux/macOS:
   source ia/.venv/bin/activate

   python -m pip install -r ia/requirements.txt
   ```

2. Configura las variables en `ia/.env` (y credenciales de AWS para Bedrock):

   ```env
   AWS_REGION=us-east-2
   BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
   ```

3. Levanta el servidor FastAPI del tutor desde la raíz del repositorio (para que `ia` sea importable como paquete):

   ```bash
   uvicorn ia.api:app --reload --port 8000
   ```

   *(Si deseas probar el bucle interactivo por consola directamente, puedes ejecutar `python -m ia.main` y escribir `salir` para terminar).*

### 2. Backend (`backend/` - NestJS)

1. Configura `backend/.env` con tus credenciales de Supabase, `CORS_ORIGINS` y el puerto deseado (por defecto `3000`).
2. Instala dependencias y arranca el servidor (por defecto en `http://localhost:3000`):

   ```bash
   npm --prefix backend install
   npm --prefix backend run start:dev
   ```

### 3. Frontend (`frontend/` - React/Vite)

1. Configura las URLs en el `.env` del frontend alineadas con tus servicios activos (por ejemplo `VITE_API_URL=http://localhost:3000` para NestJS y `VITE_AI_API_URL=http://localhost:8000` para el servicio de IA). Si editas el `.env`, reinicia el servidor de Vite.
2. Instala dependencias y levanta la interfaz:

   ```bash
   npm --prefix frontend install
   npm --prefix frontend run dev
   ```

   Vite muestra la dirección local en la terminal (por defecto `http://localhost:5173`). Asegúrate de que el backend permita ese origen mediante `CORS_ORIGINS`.

## Aplicación web y ejecución con Docker

El repositorio incluye una interfaz React/Vite, una API NestJS y el servicio FastAPI del tutor.

### Ejecución con Docker

Configura `backend/.env` con `SUPABASE_URL` y una clave de servidor (`SUPABASE_SERVICE_ROLE_KEY` o `SUPABASE_SECRET_KEY`). Para las respuestas del tutor, configura credenciales de AWS con acceso a Amazon Bedrock en `ia/.env`; opcionalmente define `AWS_REGION` y `BEDROCK_MODEL_ID`.

Desde la raíz del repositorio, construye y levanta los servicios:

```bash
docker compose up --build -d
```

Puedes comprobar los contenedores con `docker compose ps` y la salud del servicio de IA en `http://localhost:8000/health` (revisando en `docker-compose.yml` los puertos publicados para cada servicio y asegurándote de que `VITE_API_URL` y `VITE_AI_API_URL` coincidan con los puertos/URLs expuestos en tu entorno antes de construir la imagen del frontend).

### Funcionalidad conectada

- **Cuenta:** `POST /auth/register`, `POST /auth/login` y `GET /users/me` (con `SupabaseAuthGuard`). El registro puede requerir confirmación de correo según la configuración de Supabase; en ese caso, inicia sesión después de confirmarlo.
- **Panel y diagnóstico:** `GET /students/dashboard`, `GET /students/diagnostic/questions?grade=N` y `POST /students/diagnostic`. Estas rutas requieren un token Bearer y persisten resultados en Supabase. El panel muestra los datos que la API devuelve, sin inventar progreso.
- **Tutor:** `POST /sessions/start` y `POST /chat` en el servicio de IA (`http://localhost:8000`). El historial y estado pedagógico se conservan en `sessionStorage` de la pestaña; el servicio no persiste sesiones.

La aplicación todavía no ofrece recuperación de contraseña, edición de perfil ni un endpoint de cierre de sesión en el servidor. El cierre de sesión actual elimina el token guardado en el navegador.

## Qué falta

Este proyecto todavía es un prototipo y no una plataforma lista para estudiantes o docentes. Los pendientes principales son:

- **Diagnóstico inicial:** ampliar el banco de preguntas y opciones en Supabase para cubrir más habilidades, reactivos y grados conforme avance el contenido.
- **Contenido:** ampliar el banco de ejercicios, las representaciones y las rutas de aprendizaje para aritmética, álgebra, geometría y problemas contextualizados.
- **Evaluación del razonamiento:** mejorar la validación para entender pasos matemáticos reales, no solo patrones de texto o respuestas puntuales.
- **Persistencia y perfiles:** guardar sesiones del tutor, progreso y grupos para que un docente pueda atender un salón de 45 estudiantes.
- **Panel docente:** mostrar avances, errores frecuentes, confianza y recomendaciones sin exponer respuestas innecesarias.
- **Seguridad y privacidad:** definir autenticación, protección de datos de menores, límites de uso y controles de contenido.
- **Calidad técnica:** agregar pruebas automatizadas, manejo de costos y observabilidad de Bedrock, además de estandarizar `VITE_API_URL` entre entornos locales y Docker.
- **Validación educativa:** probar con estudiantes y docentes, medir aprendizaje transferible y ajustar las estrategias con evidencia.

## Estado del proyecto

**Fase:** MVP técnico con interfaz web, API de usuarios/diagnóstico conectada a Supabase y tutor adaptativo en Python/FastAPI conectado a Bedrock.

**Prioridad actual:** validar los flujos de extremo a extremo, poblar el banco diagnóstico en Supabase y ampliar el diagnóstico y la persistencia con evidencia educativa.

## Equipo y contexto

Kaanbal Tech se desarrolla para el hackatón de UniconHub por [TheIgratxd](https://github.com/TheIgratxd).