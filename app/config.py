"""
Central configuration, loaded from environment variables / .env file.
Never hardcode secrets here — this file only reads them.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # NVIDIA — the only AI provider used by this project.
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    # Comma-separated list. The client tries them in order and falls through
    # to the next one only when NVIDIA returns a "model/function not found
    # for this account" style error — i.e. when a model simply isn't
    # provisioned for this API key, not on real failures (bad key, timeout,
    # rate limit), which should surface immediately instead of being masked.
    NVIDIA_MODELS: list[str] = [
        m.strip()
        for m in os.getenv(
            "NVIDIA_MODEL",
            "meta/llama-3.3-70b-instruct,meta/llama-3.1-8b-instruct,meta/llama-3.1-70b-instruct",
        ).split(",")
        if m.strip()
    ]

    # Firebase Admin SDK
    # Either point to a service-account JSON file, or (for platforms like
    # Render/Railway where you can't easily upload a file) paste the JSON
    # contents into FIREBASE_CREDENTIALS_JSON as a single env var.
    FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    FIREBASE_DATABASE_URL: str = os.getenv("FIREBASE_DATABASE_URL", "")

    # CORS — set to your real domain(s) in production, comma separated
    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS",
            "https://lunacare--smart-women.web.app,https://lunacare--smart-women.firebaseapp.com",
        ).split(",")
        if o.strip()
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
