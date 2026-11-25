# Kaanbal Tech

> **IA que enseña a pensar, no solo a contestar.**

Kaanbal es un prototipo de tutor de matemáticas para estudiantes de secundaria. En lugar de entregar directamente la respuesta, intenta identificar qué entiende el estudiante, detectar señales de confusión y elegir una intervención pedagógica: una pregunta diagnóstica, una representación concreta o visual, una explicación guiada, práctica independiente o un reto conceptual.

El proyecto participa en el reto de UniconHub: **IA que enseña a pensar**.

## El problema

En México, solo el 34% de los estudiantes alcanzó el nivel mínimo de competencia matemática en PISA 2022. La disponibilidad de respuestas generadas por IA puede ocultar la brecha de aprendizaje si el estudiante obtiene el resultado sin construir el razonamiento.

Kaanbal busca que la IA funcione como andamiaje: ayuda a avanzar, pero conserva el esfuerzo cognitivo del estudiante y solicita evidencia de comprensión.

## Cómo va actualmente

El repositorio contiene una aplicación web conectada con una API de usuarios y diagnóstico, y un **tutor adaptativo en Python** conectado a Amazon Bedrock:

- Un evaluador pedagógico analiza la intención, la señal de comprensión, la evidencia y posibles misconceptions del último mensaje.
- Un motor pedagógico selecciona la siguiente estrategia con base en el desempeño observado.
- Un tutor genera la intervención sin resolver automáticamente el ejercicio.
- El estado de la sesión conserva dominio conceptual, dominio procedimental y relacional, confianza, historial de estrategias, intentos y próximos pasos.
- Un validador específico para ecuaciones lineales comprueba respuestas como `x = 5` y detecta si el estudiante incluyó una justificación.
- Un administrador selecciona ejercicios de ecuaciones lineales con dificultad progresiva.
- La transferencia se marca cuando el estudiante resuelve un ejercicio de mayor dificultad, justifica su procedimiento y necesita pocas pistas.

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
├── backend/                     # NestJS: autenticación, perfil y datos de estudiantes
├── ia/                          # FastAPI y motor pedagógico conectado a Bedrock
├── docker-compose.yml           # Orquestación de los tres servicios
└── README.md
```

## Requisitos

- Python 3.10+
- Credenciales de AWS con acceso a Amazon Bedrock
- Un modelo habilitado en la región configurada, por ejemplo `us.amazon.nova-pro-v1:0`

Las dependencias actuales son `boto3`, `botocore` y `python-dotenv`. Todavía falta formalizarlas en un `requirements.txt` o `pyproject.toml`.

## Ejecución local

1. Instala las dependencias de Python:

   ```bash
   python -m pip install -r ia/requirements.txt
   ```

2. Configura tus credenciales de AWS mediante el mecanismo estándar de AWS y, opcionalmente, crea un archivo `.env`:

   ```env
   AWS_REGION=us-east-1
   BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
   ```

3. Ejecuta el modo de consola del tutor:

   ```bash
   python ia/main.py
   ```

4. Escribe `salir` para terminar. El programa muestra también el estado pedagógico de depuración de la sesión.

> No subas credenciales, claves de AWS ni archivos `.env` al repositorio.

## Aplicación web

El repositorio incluye una interfaz React/Vite, una API NestJS y el servicio FastAPI del tutor.

### Ejecución con Docker

Configura `backend/.env` con `SUPABASE_URL` y una clave de servidor (`SUPABASE_SERVICE_ROLE_KEY` o `SUPABASE_SECRET_KEY`). Para las respuestas del tutor, configura credenciales de AWS con acceso a Amazon Bedrock en `ia/.env`; opcionalmente define `AWS_REGION` y `BEDROCK_MODEL_ID`.

Desde la raíz del repositorio, construye y levanta los servicios:

```bash
docker compose up --build -d
```

La aplicación queda disponible en `http://localhost:3000`, la API NestJS en `http://localhost:3001` y el servicio de IA en `http://localhost:8000`. Puedes comprobar los contenedores con `docker compose ps` y la IA en `http://localhost:8000/health`.

La imagen del frontend incorpora las URLs de API durante el build. Para desplegar en otro host, define `VITE_API_URL` y `VITE_AI_API_URL` en el entorno de Docker Compose antes de reconstruir la imagen. Sus valores locales por defecto son `http://localhost:3001` y `http://localhost:8000`.

### Ejecución local del frontend

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Vite muestra la dirección local en la terminal (por defecto `http://localhost:5173`). Asegúrate de que las APIs permitan ese origen mediante `CORS_ORIGINS`.

### Funcionalidad conectada

- **Cuenta:** `POST /auth/register`, `POST /auth/login` y `GET /users/me`. El registro puede requerir confirmación de correo según la configuración de Supabase; en ese caso, inicia sesión después de confirmarlo.
- **Panel y diagnóstico:** `GET /students/dashboard`, `GET /students/diagnostic/questions?grade=N` y `POST /students/diagnostic`. Estas rutas requieren un token Bearer. El panel muestra los datos que la API devuelve, sin inventar progreso.
- **Tutor:** `POST /sessions/start` y `POST /chat` en el servicio de IA. El historial y estado pedagógico se conservan en `sessionStorage` de la pestaña; el servicio no persiste sesiones.

La aplicación todavía no ofrece recuperación de contraseña, edición de perfil ni un endpoint de cierre de sesión en el servidor. El cierre de sesión actual elimina el token guardado en el navegador.

## Qué falta

Este proyecto todavía es un prototipo y no una plataforma lista para estudiantes o docentes. Los pendientes principales son:

- **Diagnóstico inicial:** ampliar la evaluación breve para cubrir más habilidades que ecuaciones lineales y más grados con preguntas disponibles.
- **Contenido:** ampliar el banco de ejercicios, las representaciones y las rutas de aprendizaje para aritmética, álgebra, geometría y problemas contextualizados.
- **Evaluación del razonamiento:** mejorar la validación para entender pasos matemáticos reales, no solo patrones de texto como `x = ...`.
- **Persistencia y perfiles:** guardar sesiones, progreso y grupos para que un docente pueda atender un salón de 45 estudiantes.
- **Panel docente:** mostrar avances, errores frecuentes, confianza y recomendaciones sin exponer respuestas innecesarias.
- **Seguridad y privacidad:** definir autenticación, protección de datos de menores, límites de uso y controles de contenido.
- **Calidad técnica:** agregar `requirements.txt` o `pyproject.toml`, pruebas automatizadas, manejo de costos y observabilidad de Bedrock.
- **Validación educativa:** probar con estudiantes y docentes, medir aprendizaje transferible y ajustar las estrategias con evidencia.

## Estado del proyecto

**Fase:** MVP técnico con interfaz web, API de usuarios/diagnóstico y tutor adaptativo.

**Prioridad actual:** validar los flujos de extremo a extremo y ampliar el diagnóstico y la persistencia con evidencia educativa.

## Equipo y contexto

Kaanbal Tech se desarrolla para el hackatón de UniconHub por [TheIgratxd](https://github.com/TheIgratxd).
