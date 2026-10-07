from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

from .config import get_settings
from .routers import aviro, emergency, guardians, users

settings = get_settings()
allow_all_origins = "*" in settings.ALLOWED_ORIGINS

app = FastAPI(
    title="LunaCare Backend",
    description="Server-side API for LunaCare — proxies NVIDIA AI calls and mediates Firebase reads/writes so no secret key or open database rule is ever exposed to the browser.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else settings.ALLOWED_ORIGINS,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aviro.router)
app.include_router(users.router)
app.include_router(emergency.router)
app.include_router(guardians.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "ai": {
            "key_configured": bool(settings.NVIDIA_API_KEY.strip()),
            "base_url": settings.NVIDIA_BASE_URL,
            "models": settings.NVIDIA_MODELS,
        },
    }


@app.get("/api/health/ai-models")
async def ai_models():
    api_key = settings.NVIDIA_API_KEY.strip()
    if not api_key:
        return {"status": "error", "detail": "NVIDIA_API_KEY is not configured."}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{settings.NVIDIA_BASE_URL.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        response.raise_for_status()
        models = response.json().get("data", [])
        return {"status": "ok", "models": [model.get("id") for model in models]}
    except (httpx.HTTPError, ValueError) as exc:
        print(f"NVIDIA model catalog error: {exc}")
        return {"status": "error", "detail": "Could not read NVIDIA's live model catalog."}
