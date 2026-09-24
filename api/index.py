"""
Vercel's Python runtime auto-detects an ASGI app exported as `app` in
api/*.py and serves it as a serverless function — no code changes needed
in the FastAPI app itself, just this thin entrypoint.
"""
from app.main import app  # noqa: F401  (Vercel imports this module and finds `app`)
