from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import aviro, emergency, guardians, users

settings = get_settings()

app = FastAPI(
    title="LunaCare Backend",
    description="Server-side API for LunaCare — proxies NVIDIA AI calls and mediates Firebase reads/writes so no secret key or open database rule is ever exposed to the browser.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aviro.router)
app.include_router(users.router)
app.include_router(emergency.router)
app.include_router(guardians.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
