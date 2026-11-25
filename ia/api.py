
from fastapi import FastAPI

app = FastAPI(
    title="Kaanbal AI Service",
    description="Servicio de inteligencia artificial de Kaanbal",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "kaanbal-ai",
        "message": "Kaanbal IA está funcionando correctamente"
    }
